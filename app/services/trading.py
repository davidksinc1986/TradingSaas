from __future__ import annotations

from collections import Counter
from datetime import date
import json
import logging

from app.models import Connector, TradeLog, TradeRun, User, UserPlatformGrant
from app.services.connectors import get_client
from app.services.indicators import add_indicators
from app.services.market import synthetic_ohlcv
from app.services.ml import train_and_score
from app.services.risk import position_size
from app.services.strategies import STRATEGY_MAP
from app.services.alerts import format_user_execution_message, format_user_failure_message, send_user_telegram_alert

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


def _suggest_strategy_for_regime(regime: str) -> str:
    mapping = {
        "trending": "momentum_breakout",
        "compression": "volatility_compression_breakout",
        "high_volatility": "atr_channel_breakout",
        "ranging": "mean_reversion_zscore",
    }
    return mapping.get(regime, "ema_rsi")


def _portfolio_risk_exceeded(db, user_id: int, max_open_positions: int, max_portfolio_risk: float) -> tuple[bool, dict]:
    open_like = db.query(TradeRun).filter(
        TradeRun.user_id == user_id,
        TradeRun.status.in_(["executed", "order_submitted", "order_filled"]),
    ).count()
    estimated_portfolio_risk = open_like * max(max_portfolio_risk / max(max_open_positions, 1), 0.0)
    exceeded = open_like >= max_open_positions or estimated_portfolio_risk > max_portfolio_risk
    return exceeded, {
        "open_positions_estimate": open_like,
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


def run_strategy(
    db,
    user_id: int,
    connector_ids: list[int],
    symbols: list[str],
    timeframe: str,
    strategy_slug: str,
    risk_per_trade: float,
    min_ml_probability: float,
    use_live_if_available: bool,
    take_profit_mode: str = "percent",
    take_profit_value: float = 1.5,
    stop_loss_mode: str = "percent",
    stop_loss_value: float = 1.0,
    trailing_stop_mode: str = "percent",
    trailing_stop_value: float = 0.8,
    indicator_exit_enabled: bool = False,
    indicator_exit_rule: str = "macd_cross",
    leverage_profile: str = "none",
    max_open_positions: int = 1,
    compound_growth_enabled: bool = False,
    atr_volatility_filter_enabled: bool = True,
    run_source: str = "manual",
    bot_session_id: int | None = None,
):
    base_strategy_fn = STRATEGY_MAP[strategy_slug]
    user = db.query(User).filter(User.id == user_id).first()
    connectors = db.query(Connector).filter(
        Connector.user_id == user_id,
        Connector.id.in_(connector_ids),
        Connector.is_enabled.is_(True),
    ).all()
    outputs = []

    for connector in connectors:
        client = get_client(connector)
        cfg = connector.config_json or {}
        dynamic_risk_enabled = bool(cfg.get("dynamic_risk_enabled", True))
        auto_regime_switch = bool(cfg.get("auto_regime_switch", True))
        multi_tf_confirmation_enabled = bool(cfg.get("multi_tf_confirmation_enabled", True))
        cooldown_candles = int(cfg.get("cooldown_candles", 1) or 1)
        max_portfolio_risk = float(cfg.get("max_portfolio_risk", 0.05) or 0.05)
        extreme_move_halt_pct = float(cfg.get("extreme_move_halt_pct", 0.05) or 0.05)
        smart_select_top_n = int(cfg.get("smart_select_top_n", 0) or 0)

        symbols_to_run = list(symbols)
        if smart_select_top_n > 0 and len(symbols) > smart_select_top_n:
            ranked = []
            for symbol in symbols:
                tmp = add_indicators(synthetic_ohlcv(symbol=symbol, timeframe=timeframe))
                if tmp.empty:
                    continue
                row = tmp.iloc[-1]
                score = float(row.get("ret_5", 0) or 0) + float(row.get("vol_10", 0) or 0)
                ranked.append((score, symbol))
            ranked.sort(reverse=True)
            symbols_to_run = [sym for _, sym in ranked[:smart_select_top_n]] or symbols_to_run

        for raw_symbol in symbols_to_run:
            # 1) scanner de señales
            df_raw = synthetic_ohlcv(symbol=raw_symbol, timeframe=timeframe)
            df = add_indicators(df_raw)
            if df.empty:
                continue
            row = df.iloc[-1]
            signal = base_strategy_fn(df_raw)
            prob = train_and_score(df_raw)
            price = float(row["close"])
            candle_snapshot = {
                "open": round(float(row["open"]), 6),
                "high": round(float(row["high"]), 6),
                "low": round(float(row["low"]), 6),
                "close": round(float(row["close"]), 6),
                "volume": round(float(row["volume"]), 6),
            }
            logger.info("[RAW_MARKET_DATA] symbol=%s open=%s high=%s low=%s close=%s", raw_symbol, candle_snapshot["open"], candle_snapshot["high"], candle_snapshot["low"], candle_snapshot["close"])
            logger.info("[PRICE_CHECK] symbol=%s entry_price=%s close_price=%s", raw_symbol, price, candle_snapshot["close"])

            regime = _detect_market_regime(row)
            active_strategy_slug = strategy_slug
            if auto_regime_switch:
                suggested = _suggest_strategy_for_regime(regime)
                if suggested in STRATEGY_MAP:
                    active_strategy_slug = suggested
                    signal = STRATEGY_MAP[active_strategy_slug](df_raw)

            # 2) normalizador de símbolo
            symbol_info = client.normalize_symbol(raw_symbol) if hasattr(client, "normalize_symbol") else {
                "input_symbol": raw_symbol,
                "normalized_symbol": raw_symbol,
                "exchange_symbol": str(raw_symbol).replace("/", ""),
                "found": True,
            }
            normalized_symbol = symbol_info.get("normalized_symbol") or raw_symbol
            exchange_symbol = symbol_info.get("exchange_symbol") or str(normalized_symbol).replace("/", "")
            logger.info("[ORDER_SYMBOL] display_symbol=%s exchange_symbol=%s", raw_symbol, exchange_symbol)

            # 3) cálculo de size
            connector_balance = connector_balance_hint(connector)
            stop_pct = float((cfg or {}).get("stop_pct", 0.01))
            risk_pct = float(risk_per_trade)
            atr_now = float(row.get("atr", 0) or 0)
            if dynamic_risk_enabled and atr_now > 0 and price > 0:
                atr_ratio = min(max(atr_now / price, 0.002), 0.2)
                risk_pct = min(max(risk_per_trade * (0.01 / atr_ratio), risk_per_trade * 0.5), risk_per_trade * 1.5)

            risk_usdt = connector_balance * risk_pct
            position_notional = risk_usdt / max(stop_pct, 0.0001)
            theoretical_qty = position_notional / max(price, 0.0000001)

            trade_mode = (getattr(user, "trade_amount_mode", "fixed_usd") or "fixed_usd").lower()
            fixed_amount = max(5.0, float(getattr(user, "fixed_trade_amount_usd", 10) or 10))
            balance_percent = float(getattr(user, "trade_balance_percent", 10) or 10)
            allocation_usd = max(5.0, connector_balance * max(0.0, min(balance_percent, 100.0)) / 100.0) if trade_mode == "balance_percent" else fixed_amount
            qty = min(theoretical_qty, allocation_usd / max(price, 0.0000001))
            max_risk_amount = float((cfg or {}).get("max_risk_amount", 0) or 0)
            if max_risk_amount > 0:
                qty = min(qty, max_risk_amount / max(price, 0.0000001))
            logger.info("[SIZE_CALCULATION] balance=%s risk_pct=%s risk_usdt=%s entry_price=%s stop_loss_pct=%s position_notional=%s raw_qty=%s", round(connector_balance, 6), round(risk_pct, 6), round(risk_usdt, 6), round(price, 8), round(stop_pct, 6), round(position_notional, 6), round(theoretical_qty, 8))

            # 3.5) portfolio + position checks
            exceeded, portfolio_state = _portfolio_risk_exceeded(db, user_id, max_open_positions=max_open_positions, max_portfolio_risk=max_portfolio_risk)
            recent_same_symbol = db.query(TradeRun).filter(
                TradeRun.user_id == user_id,
                TradeRun.connector_id == connector.id,
                TradeRun.symbol == raw_symbol,
            ).order_by(TradeRun.created_at.desc()).limit(cooldown_candles).all()
            in_cooldown = any(item.status in {"executed", "order_submitted", "order_filled"} for item in recent_same_symbol)
            logger.info("[POSITION_CHECK] symbol=%s existing_position=%s max_positions=%s", raw_symbol, portfolio_state["open_positions_estimate"], max_open_positions)

            volatility_ok = True
            if atr_volatility_filter_enabled:
                atr_avg = float(row.get("atr_mean_20", 0) or 0)
                volatility_ok = atr_now > atr_avg if atr_avg > 0 else True

            extreme_move = abs(float(row.get("ret_5", 0) or 0)) >= extreme_move_halt_pct
            ml_ok = (signal == "sell" or prob >= min_ml_probability)
            should_execute = signal != "hold" and ml_ok and volatility_ok and not exceeded and not in_cooldown and not extreme_move
            effective_mode = "live" if (use_live_if_available and connector.mode == "live") else connector.mode

            confirmation = {"enabled": multi_tf_confirmation_enabled, "status": "skipped", "timeframe": None, "trend": None}
            if multi_tf_confirmation_enabled:
                confirm_tf = _timeframe_for_confirmation(timeframe)
                confirm_df = add_indicators(synthetic_ohlcv(symbol=raw_symbol, timeframe=confirm_tf))
                if not confirm_df.empty:
                    c_row = confirm_df.iloc[-1]
                    trend = "buy" if float(c_row.get("ema_fast", 0)) >= float(c_row.get("ema_slow", 0)) else "sell"
                    confirmation = {"enabled": True, "status": "passed" if signal == trend else "rejected", "timeframe": confirm_tf, "trend": trend}
                    if signal in {"buy", "sell"} and signal != trend:
                        should_execute = False

            common_note = {
                "mode": effective_mode,
                "timeframe": timeframe,
                "strategy": active_strategy_slug,
                "strategy_requested": strategy_slug,
                "market_regime": regime,
                "scanner": {
                    "signal": signal,
                    "ml_probability": round(prob, 6),
                    "candle": candle_snapshot,
                },
                "symbol_normalization": symbol_info,
                "run_source": run_source,
                "bot_session_id": bot_session_id,
                "trade_amount_mode": trade_mode,
                "allocation_usd": round(allocation_usd, 4),
                "size_model": {
                    "risk_per_trade": risk_pct,
                    "risk_usdt": round(float(risk_usdt), 8),
                    "stop_pct": stop_pct,
                    "position_notional": round(float(position_notional), 8),
                    "theoretical_qty": round(float(theoretical_qty), 8),
                    "capped_qty": round(float(qty), 8),
                },
                "portfolio_risk": portfolio_state,
                "cooldown_active": in_cooldown,
                "circuit_breaker_triggered": extreme_move,
                "multi_timeframe_confirmation": confirmation,
                "take_profit_mode": take_profit_mode,
                "take_profit_value": take_profit_value,
                "stop_loss_mode": stop_loss_mode,
                "stop_loss_value": stop_loss_value,
                "trailing_stop_mode": trailing_stop_mode,
                "trailing_stop_value": trailing_stop_value,
                "indicator_exit_enabled": bool(indicator_exit_enabled),
                "indicator_exit_rule": indicator_exit_rule,
                "leverage_profile": leverage_profile,
                "max_open_positions": max_open_positions,
                "compound_growth_enabled": bool(compound_growth_enabled),
                "atr_volatility_filter_enabled": bool(atr_volatility_filter_enabled),
            }

            trade_run = TradeRun(
                user_id=user_id,
                connector_id=connector.id,
                strategy_slug=active_strategy_slug,
                symbol=raw_symbol,
                timeframe=timeframe,
                signal=signal,
                ml_probability=prob,
                quantity=qty,
                status="signal_buy" if should_execute and signal == "buy" else ("signal_sell" if should_execute and signal == "sell" else "signal_hold"),
                notes=json.dumps({**common_note, "decision": "pending"}),
            )
            db.add(trade_run)

            if not should_execute:
                reason_code = "skipped_signal_or_filters"
                if signal == "hold":
                    reason_code = "signal_hold"
                elif not ml_ok:
                    reason_code = "skipped_low_confidence"
                elif exceeded:
                    reason_code = "skipped_max_positions"
                elif in_cooldown:
                    reason_code = "skipped_cooldown"
                elif extreme_move:
                    reason_code = "skipped_circuit_breaker"
                elif confirmation.get("status") == "rejected":
                    reason_code = "skipped_multitimeframe_mismatch"
                trade_run.status = reason_code
                trade_run.notes = json.dumps({**common_note, "decision": "no_action", "reason_code": reason_code})
                outputs.append({"connector": connector.label, "platform": connector.platform, "symbol": raw_symbol, "signal": signal, "ml_probability": round(prob, 4), "status": reason_code})
                continue

            # 4) validación contra filtros del exchange
            validation = client.pretrade_validate(normalized_symbol, qty, price) if hasattr(client, "pretrade_validate") else {
                "ok": qty > 0,
                "normalized_quantity": qty,
                "normalized_price": price,
                "reason_code": "ok" if qty > 0 else "rejected_invalid_quantity",
                "exchange_filters": {},
            }
            final_qty = float(validation.get("normalized_quantity") or 0)
            final_price = float(validation.get("normalized_price") or price)
            logger.info("[EXCHANGE_FILTERS] symbol=%s min_qty=%s step_size=%s tick_size=%s qty_after_round=%s", raw_symbol, validation.get("exchange_filters", {}).get("min_qty"), validation.get("exchange_filters", {}).get("step_size"), validation.get("exchange_filters", {}).get("tick_size"), round(final_qty, 8))

            if not validation.get("ok"):
                reason_code = validation.get("reason_code") or "rejected_exchange_filter"
                trade_run.status = reason_code
                trade_run.notes = json.dumps({**common_note, "decision": signal, "validation": validation, "order_status": reason_code, "reason_code": reason_code})
                outputs.append({"connector": connector.label, "platform": connector.platform, "symbol": raw_symbol, "signal": signal, "ml_probability": round(prob, 4), "status": reason_code, "reason_code": reason_code})
                continue

            if final_qty <= 0:
                trade_run.status = "rejected_invalid_quantity"
                trade_run.notes = json.dumps({**common_note, "decision": signal, "order_status": "rejected", "reason_code": "rejected_invalid_quantity", "validation": validation})
                outputs.append({"connector": connector.label, "platform": connector.platform, "symbol": raw_symbol, "signal": signal, "ml_probability": round(prob, 4), "status": "rejected_invalid_quantity", "reason_code": "rejected_invalid_quantity"})
                continue

            # 5) envío de orden
            original_mode = connector.mode
            if connector.mode == "live" and not use_live_if_available:
                connector.mode = "paper"
            leverage = cfg.get("leverage")
            margin_type = cfg.get("margin_type", "cross")
            logger.info("[ORDER_PAYLOAD] symbol=%s side=%s order_type=market quantity=%s leverage=%s margin_type=%s", exchange_symbol, signal, round(final_qty, 8), leverage, margin_type)
            try:
                enforce_daily_limit(db, connector)
                result = client.execute_market(symbol=normalized_symbol, side=signal, quantity=final_qty, price_hint=final_price)
            except Exception as exc:
                logger.warning("[ORDER_ERROR] symbol=%s error_message=%s", raw_symbol, str(exc))
                trade_run.status = "rejected_exchange"
                trade_run.notes = json.dumps({**common_note, "decision": signal, "order_status": "rejected", "reason_code": "rejected_exchange", "validation": validation, "exchange_error": str(exc)})
                outputs.append({"connector": connector.label, "platform": connector.platform, "symbol": raw_symbol, "signal": signal, "ml_probability": round(prob, 4), "status": "rejected_exchange", "reason_code": "rejected_exchange", "message": str(exc)})
                if user:
                    send_user_telegram_alert(user, format_user_failure_message(
                        locale=user.alert_language,
                        scope="trade_execution",
                        detail=str(exc),
                        connector_label=connector.label,
                        platform=connector.platform,
                        symbol=raw_symbol,
                    ))
                continue
            finally:
                connector.mode = original_mode

            # 6) colocación de SL/TP (registrado como intención operativa)
            fill_price = float(result.fill_price or final_price)
            if signal == "buy":
                stop_loss_price = fill_price * (1 - (stop_loss_value / 100)) if stop_loss_mode == "percent" else max(fill_price - stop_loss_value, 0)
                take_profit_price = fill_price * (1 + (take_profit_value / 100)) if take_profit_mode == "percent" else fill_price + take_profit_value
            else:
                stop_loss_price = fill_price * (1 + (stop_loss_value / 100)) if stop_loss_mode == "percent" else fill_price + stop_loss_value
                take_profit_price = fill_price * (1 - (take_profit_value / 100)) if take_profit_mode == "percent" else max(fill_price - take_profit_value, 0)
            logger.info("[EXIT_PLAN] tp_pct=%s sl_pct=%s trailing_pct=%s tp_price=%s sl_price=%s", take_profit_value, stop_loss_value, trailing_stop_value, round(take_profit_price, 8), round(stop_loss_price, 8))

            # 7) persistencia/log
            result_status = str(result.status or "submitted").lower()
            final_status = "order_filled" if "filled" in result_status else "order_submitted"
            db.add(TradeLog(
                user_id=user_id,
                connector_id=connector.id,
                platform=connector.platform,
                symbol=normalized_symbol,
                side=signal,
                quantity=result.quantity,
                price=result.fill_price,
                status=final_status,
                pnl=0.0,
                meta_json={
                    "message": result.message,
                    "raw": result.raw,
                    "strategy_slug": active_strategy_slug,
                    "reason_code": final_status,
                    "take_profit_mode": take_profit_mode,
                    "take_profit_value": take_profit_value,
                    "stop_loss_mode": stop_loss_mode,
                    "stop_loss_value": stop_loss_value,
                    "trailing_stop_mode": trailing_stop_mode,
                    "trailing_stop_value": trailing_stop_value,
                    "indicator_exit_enabled": bool(indicator_exit_enabled),
                    "indicator_exit_rule": indicator_exit_rule,
                    "risk_orders": {
                        "stop_loss_price": round(float(stop_loss_price), 8),
                        "take_profit_price": round(float(take_profit_price), 8),
                        "trailing_stop_mode": trailing_stop_mode,
                        "trailing_stop_value": trailing_stop_value,
                    },
                    "validation": validation,
                    "symbol_normalization": symbol_info,
                },
            ))
            trade_run.status = final_status
            trade_run.notes = json.dumps({**common_note, "decision": signal, "order_status": final_status, "reason_code": final_status, "validation": validation, "risk_orders": {"stop_loss_price": round(float(stop_loss_price), 8), "take_profit_price": round(float(take_profit_price), 8)}, "execution_message": result.message})

            outputs.append({"connector": connector.label, "platform": connector.platform, "symbol": raw_symbol, "normalized_symbol": normalized_symbol, "signal": signal, "ml_probability": round(prob, 4), "quantity": result.quantity, "fill_price": result.fill_price, "status": final_status, "reason_code": final_status, "message": result.message})
            if user:
                send_user_telegram_alert(user, format_user_execution_message(
                    locale=user.alert_language,
                    connector_label=connector.label,
                    platform=connector.platform,
                    symbol=raw_symbol,
                    side=signal,
                    quantity=result.quantity,
                    fill_price=result.fill_price,
                    status=final_status,
                    strategy_slug=active_strategy_slug,
                    message=result.message,
                ))

    db.commit()
    return outputs


def activity_metrics(db, user_id: int) -> dict:
    trades = db.query(TradeLog).filter(TradeLog.user_id == user_id).order_by(TradeLog.created_at.asc()).all()
    equity = 1.0
    curve = []
    peak = 1.0
    drawdown = []
    monthly = {}
    yearly = {}
    wins = 0
    losses = 0
    gross_profit = 0.0
    gross_loss = 0.0

    for t in trades:
        pnl = float(t.pnl or 0)
        if pnl > 0:
            wins += 1
            gross_profit += pnl
        elif pnl < 0:
            losses += 1
            gross_loss += abs(pnl)
        equity += pnl / 100.0
        curve.append({"x": t.created_at.isoformat(), "y": round(equity, 6)})
        peak = max(peak, equity)
        dd = ((equity - peak) / peak) * 100 if peak else 0.0
        drawdown.append({"x": t.created_at.isoformat(), "y": round(dd, 4)})
        m_key = t.created_at.strftime("%Y-%m")
        y_key = t.created_at.strftime("%Y")
        monthly[m_key] = monthly.get(m_key, 0.0) + pnl
        yearly[y_key] = yearly.get(y_key, 0.0) + pnl

    total = len(trades)
    win_rate = (wins / total * 100) if total else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)
    returns = [float(t.pnl or 0) / 100.0 for t in trades if t.pnl is not None]
    avg_ret = sum(returns) / len(returns) if returns else 0.0
    std_ret = (sum((r - avg_ret) ** 2 for r in returns) / max(len(returns), 1)) ** 0.5 if returns else 0.0
    sharpe = (avg_ret / std_ret * (252 ** 0.5)) if std_ret > 0 else 0.0
    max_dd = min([d["y"] for d in drawdown], default=0.0)

    return {
        "equity_curve": curve,
        "drawdown_curve": drawdown,
        "monthly_returns": [{"period": k, "value": round(v, 4)} for k, v in sorted(monthly.items())],
        "yearly_returns": [{"period": k, "value": round(v, 4)} for k, v in sorted(yearly.items())],
        "summary": {
            "sharpe_ratio": round(sharpe, 4),
            "max_drawdown": round(max_dd, 4),
            "profit_factor": round(profit_factor, 4),
            "win_rate": round(win_rate, 2),
            "total_trades": total,
        },
    }


def dashboard_data(db, user_id: int):
    connectors = db.query(Connector).filter(Connector.user_id == user_id).all()
    trades = db.query(TradeLog).filter(TradeLog.user_id == user_id).order_by(TradeLog.created_at.desc()).limit(20).all()
    all_trades = db.query(TradeLog).filter(TradeLog.user_id == user_id).all()
    grants = db.query(UserPlatformGrant).filter(UserPlatformGrant.user_id == user_id).all()
    pnl = sum(t.pnl for t in all_trades)
    total_invested = sum((t.quantity or 0) * (t.price or 0) for t in all_trades)
    pnl_percent = (pnl / total_invested * 100) if total_invested > 0 else 0.0
    wins = sum(1 for t in all_trades if (t.pnl or 0) > 0)
    losses = sum(1 for t in all_trades if (t.pnl or 0) < 0)
    platform_counts = Counter(c.platform for c in connectors)
    status_counts = Counter(t.status for t in all_trades)

    return {
        "total_connectors": len(connectors),
        "enabled_connectors": sum(1 for c in connectors if c.is_enabled),
        "total_trades": len(all_trades),
        "realized_pnl": round(pnl, 2),
        "total_invested": round(total_invested, 2),
        "realized_pnl_percent": round(pnl_percent, 2),
        "winning_trades": wins,
        "losing_trades": losses,
        "platforms": dict(platform_counts),
        "statuses": dict(status_counts),
        "latest_trades": trades,
        "limits": [
            {
                "platform": g.platform,
                "enabled": g.is_enabled,
                "max_symbols": g.max_symbols,
                "max_daily_movements": g.max_daily_movements,
                "notes": g.notes,
            }
            for g in grants
        ]
    }
