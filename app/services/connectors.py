davidksinc@trading-bot-saas:~/TradingSaas$ sed -n '1,300p' app/services/trading.py
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
import json
import logging

from app.models import Connector, OpenPosition, TradeLog, TradeRun, User, UserPlatformGrant
from app.services.alerts import format_user_execution_message, format_user_failure_message, send_user_telegram_alert
from app.services.connectors import get_client
from app.services.indicators import add_indicators
from app.services.market import synthetic_ohlcv
from app.services.ml import train_and_score
from app.services.scanner import select_symbols_for_run
from app.services.strategies import STRATEGY_MAP, get_strategy_rule

logger = logging.getLogger("trading_saas.trading")


def connector_balance_hint(connector: Connector) -> float:
    default_balance = float((connector.config_json or {}).get("paper_balance", 10000))
    return max(default_balance, 100.0)


def enforce_daily_limit(db, connector: Connector):
    grant = db.query(UserPlatformGrant).filter(
        UserPlatformGrant.user_id == connector.user_id,
        UserPlatformGrant.platform == connector.platform,
    ).first()
    if not grant:
        return
    today = date.today().isoformat()
    count = db.query(TradeLog).filter(
        TradeLog.user_id == connector.user_id,
        TradeLog.connector_id == connector.id,
    ).all()
    count_today = sum(1 for item in count if item.created_at.date().isoformat() == today)
    if count_today >= grant.max_daily_movements:
        raise RuntimeError(f"Daily movement limit reached for {connector.platform}: {grant.max_daily_movements}")


def _detect_market_regime(row) -> str:
    adx = float(row.get("adx", 0) or 0)
    bb_width = float(row.get("bb_width", 0) or 0)
    atr_contraction = float(row.get("atr_contraction", 1) or 1)
    if adx >= 25:
        return "trending"
    if bb_width < 0.03 and atr_contraction < 0.95:
        return "compression"
    if bb_width > 0.08:
        return "high_volatility"
    return "ranging"


def _suggest_strategy_for_regime(regime: str, market_type: str) -> str:
    spot_mapping = {
        "trending": "ema_rsi_adx_stack",
        "compression": "volatility_compression_breakout",
        "high_volatility": "stochastic_rebound",
        "ranging": "mean_reversion_zscore",
    }
    futures_mapping = {
        "trending": "momentum_breakout",
        "compression": "volatility_compression_breakout",
        "high_volatility": "atr_channel_breakout",
        "ranging": "macd_trend_pullback",
    }
    mapping = futures_mapping if market_type == "futures" else spot_mapping
    return mapping.get(regime, "ema_rsi" if market_type == "spot" else "momentum_breakout")


def _portfolio_risk_exceeded(db, user_id: int, max_open_positions: int, max_portfolio_risk: float) -> tuple[bool, dict]:
    if max_open_positions <= 0:
        open_count = db.query(OpenPosition).filter(
            OpenPosition.user_id == user_id,
            OpenPosition.is_open.is_(True),
            OpenPosition.current_qty > 0,
        ).count()
        return False, {
            "open_positions_estimate": open_count,
            "max_open_positions": "unlimited",
            "estimated_portfolio_risk": 0.0,
            "max_portfolio_risk": round(float(max_portfolio_risk), 4),
        }

    open_count = db.query(OpenPosition).filter(
        OpenPosition.user_id == user_id,
        OpenPosition.is_open.is_(True),
        OpenPosition.current_qty > 0,
    ).count()

    estimated_portfolio_risk = open_count * max(max_portfolio_risk / max(max_open_positions, 1), 0.0)
    exceeded = open_count >= max_open_positions or estimated_portfolio_risk > max_portfolio_risk

    return exceeded, {
        "open_positions_estimate": open_count,
        "max_open_positions": max_open_positions,
        "estimated_portfolio_risk": round(float(estimated_portfolio_risk), 4),
        "max_portfolio_risk": round(float(max_portfolio_risk), 4),
    }


def _timeframe_for_confirmation(base_timeframe: str) -> str:
    tf = (base_timeframe or "").lower()
    if tf in {"1m", "3m", "5m", "15m", "30m"}:
        return "4h"
    if tf in {"1h", "2h"}:
        return "1d"
    return "4h"


def _is_exit_intent(intent: str) -> bool:
    return intent in {"close_long", "close_short", "sell_spot_exit"}


def _get_open_position(db, user_id: int, connector_id: int, symbol: str, position_side: str) -> OpenPosition | None:
    return db.query(OpenPosition).filter(
        OpenPosition.user_id == user_id,
        OpenPosition.connector_id == connector_id,
        OpenPosition.symbol == symbol,
        OpenPosition.position_side == position_side,
        OpenPosition.is_open.is_(True),
    ).order_by(OpenPosition.updated_at.desc()).first()


def _build_db_position_context(db, connector: Connector, symbol: str, market_type: str) -> dict:
    long_pos = _get_open_position(db, connector.user_id, connector.id, symbol, "long")
    short_pos = _get_open_position(db, connector.user_id, connector.id, symbol, "short")

    long_qty = float(long_pos.current_qty or 0.0) if long_pos else 0.0
    short_qty = float(short_pos.current_qty or 0.0) if short_pos else 0.0

    if market_type == "spot":
        return {
            "market_type": "spot",
            "symbol": symbol,
            "has_position": long_qty > 0,
            "spot_base_free": long_qty,
            "spot_base_total": long_qty,
            "net_contracts": 0.0,
            "side": "long" if long_qty > 0 else None,
            "db_entry_price": float(long_pos.entry_price or 0.0) if long_pos else 0.0,
        }

    net_contracts = long_qty - short_qty
    detected_side = None
    if net_contracts > 0:
        detected_side = "long"
    elif net_contracts < 0:
        detected_side = "short"

    return {
        "market_type": "futures",
        "symbol": symbol,
        "has_position": net_contracts != 0,
        "spot_base_free": 0.0,
        "spot_base_total": 0.0,
        "net_contracts": net_contracts,
        "side": detected_side,
        "db_long_qty": long_qty,
        "db_short_qty": short_qty,
        "db_long_entry": float(long_pos.entry_price or 0.0) if long_pos else 0.0,
        "db_short_entry": float(short_pos.entry_price or 0.0) if short_pos else 0.0,
    }


def _effective_position_context(db, connector: Connector, client, symbol: str, market_type: str) -> dict:
    db_ctx = _build_db_position_context(db, connector, symbol, market_type)
    exchange_ctx = {}

    try:
        if hasattr(client, "fetch_position_context"):
            exchange_ctx = client.fetch_position_context(symbol) or {}
    except Exception as exc:
        logger.warning("[POSITION_CONTEXT] symbol=%s exchange_context_error=%s", symbol, str(exc))
        exchange_ctx = {}

    mode_is_live = connector.mode == "live"

    if market_type == "spot":
        if mode_is_live and exchange_ctx:
            spot_qty = float(exchange_ctx.get("spot_base_free") or exchange_ctx.get("spot_base_total") or 0.0)
            return {
                **db_ctx,
                **exchange_ctx,
                "effective_source": "exchange",
                "effective_spot_qty": spot_qty,
            }
        return {
            **db_ctx,
            **exchange_ctx,
            "effective_source": "db",
            "effective_spot_qty": float(db_ctx.get("spot_base_free") or 0.0),
        }

    if mode_is_live and exchange_ctx:
        net_contracts = float(exchange_ctx.get("net_contracts") or 0.0)
        return {
            **db_ctx,
            **exchange_ctx,
            "effective_source": "exchange",
            "effective_net_contracts": net_contracts,
        }

    return {
        **db_ctx,
        **exchange_ctx,
        "effective_source": "db",
        "effective_net_contracts": float(db_ctx.get("net_contracts") or 0.0),
    }


def _resolve_trade_plan(
    db,
    connector,
    client,
    strategy_slug: str,
    signal: str,
    normalized_symbol: str,
    desired_qty: float,
    price_hint: float,
    cfg: dict,
) -> dict:
    market_type = (getattr(connector, "market_type", None) or cfg.get("market_type") or "spot").lower()
    strategy_rule = get_strategy_rule(strategy_slug)
    allow_short = bool(strategy_rule.get("allow_short", False))

    if signal == "hold":
        return {"execute": False, "reason_code": "signal_hold", "intent": "none"}

    ctx = _effective_position_context(db, connector, client, normalized_symbol, market_type)

    if market_type == "spot":
        if signal == "buy":
            return {
                "execute": True,
                "intent": "open_long",
                "side": "buy",
                "quantity": float(desired_qty),
                "reduce_only": False,
                "position_context": ctx,
            }

        available_qty = float(ctx.get("effective_spot_qty") or 0.0)
        if available_qty <= 0:
            return {
                "execute": False,
                "reason_code": "skipped_no_spot_balance",
                "intent": "none",
                "position_context": ctx,
            }

        sell_full_balance = bool(cfg.get("spot_sell_full_balance", True))
        sell_qty = available_qty if sell_full_balance else min(float(desired_qty), available_qty)
        if sell_qty <= 0:
            return {
                "execute": False,
                "reason_code": "rejected_invalid_quantity",
                "intent": "none",
                "position_context": ctx,
            }

        return {
            "execute": True,
            "intent": "sell_spot_exit",
            "side": "sell",
            "quantity": float(sell_qty),
            "reduce_only": False,
            "position_context": ctx,
        }

    net_contracts = float(ctx.get("effective_net_contracts") or 0.0)

    if signal == "buy":
        if net_contracts < 0:
            return {
                "execute": True,
                "intent": "close_short",
                "side": "buy",
                "quantity": abs(net_contracts),
                "reduce_only": True,
                "position_context": ctx,
            }
        return {
            "execute": True,
            "intent": "open_long",
            "side": "buy",
            "quantity": float(desired_qty),
            "reduce_only": False,
            "position_context": ctx,
        }

    if signal == "sell":
        if net_contracts > 0:
            return {
                "execute": True,
                "intent": "close_long",
                "side": "sell",
                "quantity": abs(net_contracts),
                "reduce_only": True,
davidksinc@trading-bot-saas:~/TradingSaas$ 
