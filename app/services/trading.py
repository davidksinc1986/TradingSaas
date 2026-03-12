from __future__ import annotations

from collections import Counter
from datetime import date

from app.models import Connector, TradeLog, TradeRun, UserPlatformGrant
from app.services.connectors import get_client
from app.services.market import synthetic_ohlcv
from app.services.ml import train_and_score
from app.services.risk import position_size
from app.services.strategies import STRATEGY_MAP


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



def run_strategy(db, user_id: int, connector_ids: list[int], symbols: list[str], timeframe: str,
                 strategy_slug: str, risk_per_trade: float, min_ml_probability: float, use_live_if_available: bool):
    strategy_fn = STRATEGY_MAP[strategy_slug]
    connectors = db.query(Connector).filter(
        Connector.user_id == user_id,
        Connector.id.in_(connector_ids),
        Connector.is_enabled.is_(True),
    ).all()
    outputs = []

    for connector in connectors:
        client = get_client(connector)
        for symbol in symbols:
            df = synthetic_ohlcv(symbol=symbol, timeframe=timeframe)
            signal = strategy_fn(df)
            price = float(df.iloc[-1]["close"])
            prob = train_and_score(df)
            qty = position_size(
                balance=connector_balance_hint(connector),
                risk_per_trade=risk_per_trade,
                price=price,
                stop_pct=float((connector.config_json or {}).get("stop_pct", 0.01)),
            )
            max_risk_amount = float((connector.config_json or {}).get("max_risk_amount", 0) or 0)
            if max_risk_amount > 0:
                qty = min(qty, max_risk_amount / max(price, 0.0000001))

            should_execute = signal != "hold" and prob >= min_ml_probability
            effective_mode = "live" if (use_live_if_available and connector.mode == "live") else connector.mode

            trade_run = TradeRun(
                user_id=user_id,
                connector_id=connector.id,
                strategy_slug=strategy_slug,
                symbol=symbol,
                timeframe=timeframe,
                signal=signal,
                ml_probability=prob,
                quantity=qty,
                status="ready" if should_execute else "skipped",
                notes=f"mode={effective_mode}",
            )
            db.add(trade_run)

            if not should_execute:
                outputs.append({
                    "connector": connector.label,
                    "platform": connector.platform,
                    "symbol": symbol,
                    "signal": signal,
                    "ml_probability": round(prob, 4),
                    "status": "skipped",
                })
                continue

            original_mode = connector.mode
            if connector.mode == "live" and not use_live_if_available:
                connector.mode = "paper"
            try:
                enforce_daily_limit(db, connector)
                result = client.execute_market(symbol=symbol, side=signal, quantity=qty, price_hint=price)
            finally:
                connector.mode = original_mode

            db.add(TradeLog(
                user_id=user_id,
                connector_id=connector.id,
                platform=connector.platform,
                symbol=symbol,
                side=signal,
                quantity=result.quantity,
                price=result.fill_price,
                status=result.status,
                pnl=0.0,
                meta_json={"message": result.message, "raw": result.raw, "strategy_slug": strategy_slug},
            ))

            outputs.append({
                "connector": connector.label,
                "platform": connector.platform,
                "symbol": symbol,
                "signal": signal,
                "ml_probability": round(prob, 4),
                "quantity": result.quantity,
                "fill_price": result.fill_price,
                "status": result.status,
                "message": result.message,
            })

    db.commit()
    return outputs



def dashboard_data(db, user_id: int):
    connectors = db.query(Connector).filter(Connector.user_id == user_id).all()
    trades = db.query(TradeLog).filter(TradeLog.user_id == user_id).order_by(TradeLog.created_at.desc()).limit(20).all()
    all_trades = db.query(TradeLog).filter(TradeLog.user_id == user_id).all()
    grants = db.query(UserPlatformGrant).filter(UserPlatformGrant.user_id == user_id).all()
    pnl = sum(t.pnl for t in all_trades)
    platform_counts = Counter(c.platform for c in connectors)
    status_counts = Counter(t.status for t in all_trades)

    return {
        "total_connectors": len(connectors),
        "enabled_connectors": sum(1 for c in connectors if c.is_enabled),
        "total_trades": len(all_trades),
        "realized_pnl": round(pnl, 2),
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
