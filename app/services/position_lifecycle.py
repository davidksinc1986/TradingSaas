from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models import Connector, OpenPosition, TradeLog, TradeRun, User
from app.services.connectors import BaseConnectorClient, get_client
from app.services.market import fetch_ohlcv_frame
from app.services.strategies import STRATEGY_MAP


LIFECYCLE_OPEN_STATES = {"pending_open", "open", "closing", "failed_close", "orphaned"}
CRITICAL_CLOSE_REASONS = {"stop_loss", "risk", "orphaned", "kill_switch", "forced", "manual", "close_retry_exhausted"}
DEFAULT_TIMEOUT_MINUTES = 240
DEFAULT_MAX_DRAWDOWN_PCT = 2.0
DEFAULT_CLOSE_RETRIES = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 0.2
FAILSAFE_FAILURE_THRESHOLD = 3


def utcnow() -> datetime:
    return datetime.utcnow()


def _safe_float(value: Any, fallback: float = 0.0) -> float:
    try:
        parsed = float(value)
        if parsed != parsed:
            return fallback
        return parsed
    except Exception:
        return fallback


def _percent_to_decimal(value: float) -> float:
    clean = _safe_float(value, 0.0)
    return clean / 100 if clean > 1 else clean


def _position_meta(position: OpenPosition) -> dict[str, Any]:
    meta = position.meta_json or {}
    if not isinstance(meta, dict):
        meta = {}
    meta.setdefault("events", [])
    meta.setdefault("exit_policy", {})
    meta.setdefault("lifecycle", {})
    return meta


def _append_event(position: OpenPosition, event_type: str, **payload: Any) -> dict[str, Any]:
    meta = _position_meta(position)
    events = list(meta.get("events") or [])
    events.append({
        "ts": utcnow().isoformat(),
        "event": event_type,
        **payload,
    })
    meta["events"] = events[-200:]
    position.meta_json = meta
    return meta


def _set_lifecycle_state(position: OpenPosition, state: str, **extra: Any) -> dict[str, Any]:
    meta = _position_meta(position)
    lifecycle = dict(meta.get("lifecycle") or {})
    lifecycle.update({
        "state": state,
        "updated_at": utcnow().isoformat(),
        **extra,
    })
    meta["lifecycle"] = lifecycle
    position.meta_json = meta
    return lifecycle


def build_exit_policy(*, stop_loss_mode: str, stop_loss_value: float, take_profit_mode: str, take_profit_value: float, trailing_stop_mode: str, trailing_stop_value: float, indicator_exit_enabled: bool = False, indicator_exit_rule: str = "macd_cross", timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES, max_drawdown_pct: float = DEFAULT_MAX_DRAWDOWN_PCT) -> dict[str, Any]:
    return {
        "stop_loss": {
            "mode": stop_loss_mode,
            "value": _safe_float(stop_loss_value),
            "enabled": _safe_float(stop_loss_value) > 0,
        },
        "take_profit": {
            "mode": take_profit_mode,
            "value": _safe_float(take_profit_value),
            "enabled": _safe_float(take_profit_value) > 0,
        },
        "trailing_stop": {
            "mode": trailing_stop_mode,
            "value": _safe_float(trailing_stop_value),
            "enabled": _safe_float(trailing_stop_value) > 0,
        },
        "indicator_exit": {
            "enabled": bool(indicator_exit_enabled),
            "rule": indicator_exit_rule,
        },
        "fallback_exit": {
            "timeout_minutes": max(int(timeout_minutes or DEFAULT_TIMEOUT_MINUTES), 1),
            "max_drawdown_pct": max(_safe_float(max_drawdown_pct, DEFAULT_MAX_DRAWDOWN_PCT), 0.1),
        },
    }


def validate_exit_policy(policy: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    stop_loss = (policy or {}).get("stop_loss") or {}
    take_profit = (policy or {}).get("take_profit") or {}
    trailing = (policy or {}).get("trailing_stop") or {}
    fallback = (policy or {}).get("fallback_exit") or {}

    if not stop_loss.get("enabled") or _safe_float(stop_loss.get("value")) <= 0:
        errors.append("missing_stop_loss")
    if not take_profit.get("enabled") and not trailing.get("enabled"):
        errors.append("missing_profit_capture_mechanism")
    if int(fallback.get("timeout_minutes") or 0) <= 0 and _safe_float(fallback.get("max_drawdown_pct")) <= 0:
        errors.append("missing_fallback_exit")
    return len(errors) == 0, errors


def ensure_position_exit_policy(position: OpenPosition) -> dict[str, Any]:
    meta = _position_meta(position)
    policy = dict(meta.get("exit_policy") or {})
    fallback = dict(policy.get("fallback_exit") or {})
    stop_loss_price = _safe_float(meta.get("stop_loss_price"), 0.0)
    take_profit_price = _safe_float(meta.get("take_profit_price"), 0.0)

    policy.setdefault("stop_loss", {
        "mode": meta.get("stop_loss_mode") or "price",
        "value": stop_loss_price,
        "enabled": stop_loss_price > 0,
    })
    policy.setdefault("take_profit", {
        "mode": meta.get("take_profit_mode") or "price",
        "value": take_profit_price,
        "enabled": take_profit_price > 0,
    })
    policy.setdefault("trailing_stop", {
        "mode": meta.get("trailing_stop_mode") or "percent",
        "value": _safe_float(meta.get("trailing_stop_value"), 0.0),
        "enabled": _safe_float(meta.get("trailing_stop_value"), 0.0) > 0,
    })
    policy.setdefault("indicator_exit", {
        "enabled": bool(meta.get("indicator_exit_enabled", False)),
        "rule": meta.get("indicator_exit_rule") or "macd_cross",
    })
    fallback.setdefault("timeout_minutes", int(meta.get("timeout_minutes") or DEFAULT_TIMEOUT_MINUTES))
    fallback.setdefault("max_drawdown_pct", _safe_float(meta.get("max_drawdown_pct"), DEFAULT_MAX_DRAWDOWN_PCT))
    policy["fallback_exit"] = fallback

    valid, errors = validate_exit_policy(policy)
    meta["exit_policy"] = policy
    meta["exit_policy_valid"] = valid
    meta["exit_policy_errors"] = errors
    if not meta.get("lifecycle"):
        meta["lifecycle"] = {"state": "open", "updated_at": utcnow().isoformat()}
    position.meta_json = meta
    return policy


def initialize_position_lifecycle(
    position: OpenPosition,
    *,
    strategy_slug: str,
    timeframe: str,
    take_profit_mode: str,
    take_profit_value: float,
    stop_loss_mode: str,
    stop_loss_value: float,
    trailing_stop_mode: str,
    trailing_stop_value: float,
    indicator_exit_enabled: bool,
    indicator_exit_rule: str,
    timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES,
    max_drawdown_pct: float = DEFAULT_MAX_DRAWDOWN_PCT,
    bot_session_id: int | None = None,
    run_source: str = "manual",
) -> None:
    meta = _position_meta(position)
    meta.update({
        "strategy_slug": strategy_slug,
        "timeframe": timeframe,
        "bot_session_id": bot_session_id,
        "run_source": run_source,
        "stop_loss_mode": stop_loss_mode,
        "take_profit_mode": take_profit_mode,
        "trailing_stop_mode": trailing_stop_mode,
        "trailing_stop_value": _safe_float(trailing_stop_value),
        "indicator_exit_enabled": bool(indicator_exit_enabled),
        "indicator_exit_rule": indicator_exit_rule,
        "timeout_minutes": max(int(timeout_minutes or DEFAULT_TIMEOUT_MINUTES), 1),
        "max_drawdown_pct": max(_safe_float(max_drawdown_pct, DEFAULT_MAX_DRAWDOWN_PCT), 0.1),
        "peak_price": _safe_float(position.entry_price),
        "trough_price": _safe_float(position.entry_price),
        "close_attempts": 0,
        "last_exit_evaluation_at": None,
    })
    meta["exit_policy"] = build_exit_policy(
        stop_loss_mode=stop_loss_mode,
        stop_loss_value=stop_loss_value,
        take_profit_mode=take_profit_mode,
        take_profit_value=take_profit_value,
        trailing_stop_mode=trailing_stop_mode,
        trailing_stop_value=trailing_stop_value,
        indicator_exit_enabled=indicator_exit_enabled,
        indicator_exit_rule=indicator_exit_rule,
        timeout_minutes=timeout_minutes,
        max_drawdown_pct=max_drawdown_pct,
    )
    meta["stop_loss_price"] = _safe_float(meta.get("stop_loss_price"), 0.0)
    meta["take_profit_price"] = _safe_float(meta.get("take_profit_price"), 0.0)
    position.meta_json = meta
    _set_lifecycle_state(position, "open")
    _append_event(position, "position_opened", strategy_slug=strategy_slug, timeframe=timeframe, run_source=run_source)
    ensure_position_exit_policy(position)


def _market_price_from_data(market_data: dict[str, Any]) -> float:
    return _safe_float((market_data or {}).get("price") or (market_data or {}).get("close"), 0.0)


def _price_hit(side: str, price: float, target: float, *, is_stop: bool) -> bool:
    if price <= 0 or target <= 0:
        return False
    if side == "long":
        return price <= target if is_stop else price >= target
    return price >= target if is_stop else price <= target


def evaluate_exit_conditions(position: OpenPosition, market_data: dict[str, Any], risk_context: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = _position_meta(position)
    policy = ensure_position_exit_policy(position)
    side = str(position.position_side or "long").lower()
    price = _market_price_from_data(market_data)
    entry_price = max(_safe_float(position.entry_price, 0.0), 0.0000001)
    now = risk_context.get("now") if risk_context else None
    if not isinstance(now, datetime):
        now = utcnow()
    opened_at = getattr(position, "opened_at", None) or now
    age_minutes = max((now - opened_at).total_seconds() / 60.0, 0.0)
    signal = str((market_data or {}).get("signal") or "hold").lower()
    force_close = bool((meta.get("lifecycle") or {}).get("force_close_requested")) or bool((risk_context or {}).get("force_close"))

    peak_price = max(_safe_float(meta.get("peak_price"), entry_price), price or entry_price)
    trough_price = min(_safe_float(meta.get("trough_price"), entry_price) or entry_price, price or entry_price)
    if side == "long":
        meta["peak_price"] = peak_price
        meta["trough_price"] = min(_safe_float(meta.get("trough_price"), entry_price) or entry_price, price or entry_price)
        drawdown_pct = max((entry_price - max(price, 0.0)) / entry_price, 0.0) * 100
    else:
        meta["trough_price"] = trough_price
        meta["peak_price"] = max(_safe_float(meta.get("peak_price"), entry_price) or entry_price, price or entry_price)
        drawdown_pct = max((max(price, 0.0) - entry_price) / entry_price, 0.0) * 100
    meta["last_exit_evaluation_at"] = now.isoformat()
    meta["last_market_price"] = price
    meta["last_strategy_signal"] = signal
    meta["drawdown_pct"] = drawdown_pct
    position.meta_json = meta

    if force_close:
        return {"should_close": True, "reason": "forced", "urgency": "critical", "price": price, "details": {"age_minutes": age_minutes}}

    stop_loss_price = _safe_float(meta.get("stop_loss_price"), 0.0)
    if policy.get("stop_loss", {}).get("enabled") and _price_hit(side, price, stop_loss_price, is_stop=True):
        return {"should_close": True, "reason": "stop_loss", "urgency": "critical", "price": price, "details": {"stop_loss_price": stop_loss_price, "age_minutes": age_minutes}}

    take_profit_price = _safe_float(meta.get("take_profit_price"), 0.0)
    if policy.get("take_profit", {}).get("enabled") and _price_hit(side, price, take_profit_price, is_stop=False):
        return {"should_close": True, "reason": "take_profit", "urgency": "high", "price": price, "details": {"take_profit_price": take_profit_price, "age_minutes": age_minutes}}

    trailing_cfg = policy.get("trailing_stop", {}) or {}
    trailing_value = _safe_float(trailing_cfg.get("value"), 0.0)
    if trailing_cfg.get("enabled") and trailing_value > 0 and price > 0:
        trailing_delta = entry_price * _percent_to_decimal(trailing_value) if trailing_cfg.get("mode") == "percent" else trailing_value
        if side == "long":
            trail_trigger = peak_price - trailing_delta
            meta["trail_trigger_price"] = trail_trigger
            position.meta_json = meta
            if peak_price > entry_price and price <= trail_trigger:
                return {"should_close": True, "reason": "trailing_stop", "urgency": "high", "price": price, "details": {"trail_trigger_price": trail_trigger, "peak_price": peak_price}}
        else:
            trail_trigger = trough_price + trailing_delta
            meta["trail_trigger_price"] = trail_trigger
            position.meta_json = meta
            if trough_price < entry_price and price >= trail_trigger:
                return {"should_close": True, "reason": "trailing_stop", "urgency": "high", "price": price, "details": {"trail_trigger_price": trail_trigger, "trough_price": trough_price}}

    if signal in {"buy", "sell"}:
        opposite_signal = (side == "long" and signal == "sell") or (side == "short" and signal == "buy")
        if opposite_signal:
            return {"should_close": True, "reason": "opposite_signal", "urgency": "normal", "price": price, "details": {"signal": signal, "age_minutes": age_minutes}}

    fallback = policy.get("fallback_exit", {}) or {}
    timeout_minutes = int(fallback.get("timeout_minutes") or DEFAULT_TIMEOUT_MINUTES)
    if age_minutes >= timeout_minutes:
        return {"should_close": True, "reason": "timeout", "urgency": "high", "price": price, "details": {"age_minutes": age_minutes, "timeout_minutes": timeout_minutes}}

    max_drawdown_pct = _safe_float(fallback.get("max_drawdown_pct"), DEFAULT_MAX_DRAWDOWN_PCT)
    if drawdown_pct >= max_drawdown_pct:
        return {"should_close": True, "reason": "risk", "urgency": "critical", "price": price, "details": {"drawdown_pct": drawdown_pct, "max_drawdown_pct": max_drawdown_pct}}

    return {"should_close": False, "reason": None, "urgency": "normal", "price": price, "details": {"age_minutes": age_minutes, "drawdown_pct": drawdown_pct}}


def translate_close_error(platform: str, detail: str) -> str:
    message = str(detail or "").lower()
    platform = str(platform or "unknown").lower()

    if "reduceonly" in message or "reduce only" in message:
        return "reduce_only_failed"
    if "position not found" in message or "no position" in message or "unknown order sent" in message:
        return "position_not_found"
    if "insufficient" in message and ("liquidity" in message or "depth" in message):
        return "insufficient_liquidity"
    if "insufficient" in message and ("balance" in message or "margin" in message or "fund" in message):
        return "close_order_rejected"
    if "invalid amount" in message or "invalid quantity" in message or "invalid volume" in message or "lot" in message:
        return "invalid_size"
    if "desync" in message or "out of sync" in message:
        return "exchange_desync"
    if "timeout" in message or "timed out" in message or "temporarily unavailable" in message:
        return "close_retryable_timeout"
    if platform in {"mt5", "metatrader", "fxcm"} and "retcode" in message:
        return "close_order_rejected"
    if platform in {"binance", "bybit", "okx"} and "reject" in message:
        return "close_order_rejected"
    return "close_order_rejected"


def _close_side(position: OpenPosition) -> str:
    return "sell" if str(position.position_side or "long").lower() == "long" else "buy"


def _position_quantity(position: OpenPosition, context: dict[str, Any]) -> float:
    market_type = str(position.market_type or "spot").lower()
    if market_type == "spot":
        return max(
            _safe_float(context.get("spot_base_free"), 0.0),
            _safe_float(context.get("spot_base_total"), 0.0),
            _safe_float(position.current_qty, 0.0),
        )
    return max(abs(_safe_float(context.get("net_contracts"), 0.0)), _safe_float(position.current_qty, 0.0))


def _mark_position_closed(position: OpenPosition, *, reason: str, exchange_context: dict[str, Any] | None = None) -> None:
    position.is_open = False
    position.current_qty = 0.0
    position.closed_at = utcnow()
    _set_lifecycle_state(position, "closed", close_reason=reason)
    _append_event(position, "position_closed", reason=reason, exchange_context=exchange_context or {})


def execute_close_position(
    db: Session,
    position: OpenPosition,
    *,
    reason: str,
    exchange_context: dict[str, Any] | None = None,
    urgency: str = "normal",
    max_attempts: int = DEFAULT_CLOSE_RETRIES,
    client: BaseConnectorClient | None = None,
) -> dict[str, Any]:
    connector = position.connector or db.query(Connector).filter(Connector.id == position.connector_id).first()
    if connector is None:
        raise RuntimeError(f"connector {position.connector_id} not found for position {position.id}")

    client = client or get_client(connector)
    _set_lifecycle_state(position, "closing", close_reason=reason, urgency=urgency)
    _append_event(position, "close_requested", reason=reason, urgency=urgency)

    last_error: str | None = None
    summary: dict[str, Any] = {"closed": False, "attempts": [], "reason": reason, "urgency": urgency}

    for attempt in range(1, max_attempts + 1):
        context_before = client.fetch_position_context(position.symbol)
        qty = _position_quantity(position, context_before)
        meta = _position_meta(position)
        meta["close_attempts"] = int(meta.get("close_attempts") or 0) + 1
        meta["last_close_reason"] = reason
        position.meta_json = meta

        if qty <= 0 or not context_before.get("has_position"):
            _mark_position_closed(position, reason="reconciled_no_exchange_position", exchange_context=context_before)
            db.add(position)
            db.commit()
            return {"closed": True, "attempt": attempt, "reason": "reconciled_no_exchange_position", "verification": context_before, "attempts": summary["attempts"]}

        order_side = _close_side(position)
        reduce_only = str(position.market_type or "spot").lower() in {"futures", "perpetual", "swap", "cfd", "forex"}
        price_hint = _safe_float((exchange_context or {}).get("price_hint") or context_before.get("mark_price") or context_before.get("last_price") or meta.get("last_market_price") or position.entry_price, position.entry_price)

        attempt_payload = {
            "attempt": attempt,
            "qty": qty,
            "side": order_side,
            "reduce_only": reduce_only,
            "context_before": context_before,
        }
        try:
            result = client.execute_market(
                symbol=position.symbol,
                side=order_side,
                quantity=qty,
                price_hint=price_hint,
                reduce_only=reduce_only,
                extra_params={"close_reason": reason, "close_attempt": attempt, "urgency": urgency},
            )
            verification = client.fetch_position_context(position.symbol)
            attempt_payload["execution"] = result.raw
            attempt_payload["verification"] = verification
            summary["attempts"].append(attempt_payload)
            _append_event(position, "close_attempt_executed", reason=reason, attempt=attempt, result=result.raw, verification=verification)

            if not verification.get("has_position") or _position_quantity(position, verification) <= 0:
                _mark_position_closed(position, reason=reason, exchange_context=verification)
                trade_log = TradeLog(
                    user_id=position.user_id,
                    connector_id=position.connector_id,
                    platform=position.platform,
                    symbol=position.symbol,
                    side=order_side,
                    quantity=float(result.quantity or qty),
                    price=float(result.fill_price or price_hint),
                    order_type="market",
                    status=result.status,
                    pnl=0.0,
                    meta_json={
                        "close_reason": reason,
                        "urgency": urgency,
                        "execution_raw": result.raw,
                        "verification": verification,
                    },
                )
                db.add(trade_log)
                db.add(position)
                db.commit()
                summary.update({"closed": True, "verification": verification, "last_status": result.status})
                return summary

            last_error = "exchange_desync"
            _append_event(position, "close_verification_failed", reason=reason, attempt=attempt, verification=verification)
        except Exception as exc:
            last_error = translate_close_error(connector.platform, str(exc))
            attempt_payload["error"] = str(exc)
            attempt_payload["error_code"] = last_error
            summary["attempts"].append(attempt_payload)
            _append_event(position, "close_attempt_failed", reason=reason, attempt=attempt, error=str(exc), error_code=last_error)

        db.add(position)
        db.commit()
        if attempt < max_attempts:
            time.sleep(DEFAULT_RETRY_BACKOFF_SECONDS * attempt)

    _set_lifecycle_state(position, "failed_close", close_reason=reason, error=last_error, escalation="critical")
    _append_event(position, "close_escalated", reason=reason, error=last_error)
    db.add(position)
    db.commit()
    summary.update({"closed": False, "error": last_error or "close_retry_exhausted"})
    return summary


def _connector_symbols(connector: Connector) -> list[str]:
    payload = connector.symbols_json or {}
    if isinstance(payload, dict):
        raw = payload.get("symbols") or payload.get("items") or []
    elif isinstance(payload, list):
        raw = payload
    else:
        raw = []
    return [str(item).strip() for item in raw if str(item).strip()]


def reconcile_positions_with_exchange(db: Session, connector: Connector, *, close_orphans: bool = True) -> dict[str, Any]:
    client = get_client(connector)
    open_rows = db.query(OpenPosition).filter(OpenPosition.connector_id == connector.id, OpenPosition.is_open.is_(True)).all()
    tracked_symbols = set(_connector_symbols(connector)) | {row.symbol for row in open_rows}
    exchange_positions = client.list_open_positions(symbols=sorted(tracked_symbols))
    exchange_by_symbol = {str(item.get("symbol")): item for item in exchange_positions if item.get("symbol")}

    resolved: list[dict[str, Any]] = []
    orphaned: list[dict[str, Any]] = []

    for row in open_rows:
        exchange_context = exchange_by_symbol.get(row.symbol)
        if exchange_context is None:
            exchange_context = client.fetch_position_context(row.symbol)

        if exchange_context.get("has_position"):
            row.current_qty = _position_quantity(row, exchange_context)
            ensure_position_exit_policy(row)
            _set_lifecycle_state(row, (row.meta_json or {}).get("lifecycle", {}).get("state") or "open")
            _append_event(row, "reconciled_position", exchange_context=exchange_context)
            resolved.append({"symbol": row.symbol, "action": "matched"})
        else:
            _mark_position_closed(row, reason="resolved_missing_on_exchange", exchange_context=exchange_context)
            resolved.append({"symbol": row.symbol, "action": "closed_missing_exchange_position"})

    tracked_db_symbols = {row.symbol for row in open_rows}
    for symbol, context in exchange_by_symbol.items():
        if symbol in tracked_db_symbols or not context.get("has_position"):
            continue
        qty = max(abs(_safe_float(context.get("net_contracts"), 0.0)), _safe_float(context.get("spot_base_total"), 0.0))
        orphan = OpenPosition(
            user_id=connector.user_id,
            connector_id=connector.id,
            platform=connector.platform,
            market_type=getattr(connector, "market_type", "spot"),
            symbol=symbol,
            position_side=context.get("side") or "long",
            entry_price=_safe_float(context.get("entry_price"), 0.0),
            current_qty=qty,
            is_open=True,
            meta_json={
                "created_by_reconciliation": True,
                "exchange_context": context,
                "timeout_minutes": 15,
                "max_drawdown_pct": 0.5,
                "exit_policy": build_exit_policy(
                    stop_loss_mode="price",
                    stop_loss_value=max(_safe_float(context.get("entry_price"), 0.0) * 0.99, 0.0),
                    take_profit_mode="price",
                    take_profit_value=max(_safe_float(context.get("entry_price"), 0.0) * 1.01, 0.0),
                    trailing_stop_mode="percent",
                    trailing_stop_value=0.0,
                    timeout_minutes=15,
                    max_drawdown_pct=0.5,
                ),
            },
        )
        db.add(orphan)
        db.flush()
        _set_lifecycle_state(orphan, "orphaned", discovered_by="reconciliation")
        _append_event(orphan, "orphan_detected", exchange_context=context)
        orphaned.append({"symbol": symbol, "position_id": orphan.id})
        if close_orphans:
            execute_close_position(db, orphan, reason="orphaned", exchange_context=context, urgency="critical", client=client)

    db.commit()
    return {
        "connector_id": connector.id,
        "resolved": resolved,
        "orphaned": orphaned,
        "synced_at": utcnow().isoformat(),
    }


def _latest_market_snapshot(connector: Connector, position: OpenPosition) -> dict[str, Any]:
    timeframe = str(((position.meta_json or {}).get("timeframe") or "5m"))
    market_result = fetch_ohlcv_frame(connector=connector, symbol=position.symbol, timeframe=timeframe, limit=220)
    frame = market_result.frame
    if frame.empty:
        return {"price": 0.0, "signal": "hold", "meta": market_result.meta}

    price = _safe_float(frame.iloc[-1]["close"], 0.0)
    signal = "hold"
    strategy_slug = (position.meta_json or {}).get("strategy_slug")
    strategy_fn = STRATEGY_MAP.get(strategy_slug)
    if strategy_fn is not None:
        try:
            signal = str(strategy_fn(frame) or "hold").lower()
        except Exception:
            signal = "hold"

    return {"price": price, "close": price, "signal": signal, "meta": market_result.meta}


def trigger_kill_switch(db: Session, *, connector_ids: list[int] | None = None, reason: str = "kill_switch") -> dict[str, Any]:
    query = db.query(OpenPosition).filter(OpenPosition.is_open.is_(True))
    if connector_ids:
        query = query.filter(OpenPosition.connector_id.in_(connector_ids))
    positions = query.order_by(OpenPosition.id.asc()).all()
    closed = []
    failed = []
    for position in positions:
        result = execute_close_position(db, position, reason=reason, urgency="critical", max_attempts=4)
        if result.get("closed"):
            closed.append(position.id)
        else:
            failed.append({"position_id": position.id, "error": result.get("error")})
    return {"triggered_at": utcnow().isoformat(), "reason": reason, "closed": closed, "failed": failed}


def run_position_lifecycle(db: Session, *, connector_ids: list[int] | None = None, max_positions: int | None = None) -> dict[str, Any]:
    connector_query = db.query(Connector).filter(Connector.is_enabled.is_(True))
    if connector_ids:
        connector_query = connector_query.filter(Connector.id.in_(connector_ids))
    connectors = connector_query.order_by(Connector.id.asc()).all()

    evaluated = 0
    closed = []
    failed_close = []
    orphaned = []

    for connector in connectors:
        reconciliation = reconcile_positions_with_exchange(db, connector, close_orphans=True)
        orphaned.extend(reconciliation.get("orphaned") or [])

        query = db.query(OpenPosition).filter(
            OpenPosition.connector_id == connector.id,
            OpenPosition.is_open.is_(True),
        ).order_by(OpenPosition.id.asc())
        if max_positions:
            query = query.limit(max_positions)
        positions = query.all()

        for position in positions:
            ensure_position_exit_policy(position)
            valid = bool((position.meta_json or {}).get("exit_policy_valid"))
            if not valid:
                _set_lifecycle_state(position, "failed_close", error="invalid_exit_policy")
                _append_event(position, "invalid_exit_policy", errors=(position.meta_json or {}).get("exit_policy_errors"))
                failed_close.append({"position_id": position.id, "reason": "invalid_exit_policy"})
                continue

            snapshot = _latest_market_snapshot(connector, position)
            evaluation = evaluate_exit_conditions(position, snapshot, {"now": utcnow()})
            _append_event(position, "exit_evaluated", evaluation=evaluation)
            db.add(position)
            db.commit()
            evaluated += 1

            if evaluation.get("should_close"):
                result = execute_close_position(
                    db,
                    position,
                    reason=str(evaluation.get("reason") or "unspecified"),
                    exchange_context={"price_hint": evaluation.get("price")},
                    urgency=str(evaluation.get("urgency") or "normal"),
                )
                if result.get("closed"):
                    closed.append({"position_id": position.id, "reason": evaluation.get("reason")})
                else:
                    failed_close.append({"position_id": position.id, "reason": evaluation.get("reason"), "error": result.get("error")})

    if len(failed_close) >= FAILSAFE_FAILURE_THRESHOLD:
        trigger_kill_switch(db, connector_ids=connector_ids, reason="kill_switch")

    return {
        "evaluated": evaluated,
        "closed": closed,
        "failed_close": failed_close,
        "orphaned": orphaned,
        "checked_at": utcnow().isoformat(),
    }
