from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta

from app.db import SessionLocal, commit_with_retry, rollback_safely
from app.models import BotSession, Connector
from app.services.connector_state import ensure_connector_market_type_state, normalize_market_type, resolve_runtime_market_type
from app.services.position_lifecycle import run_position_lifecycle
from app.services.strategies import get_strategy_rule
from app.services.trading import run_strategy

logger = logging.getLogger("trading_saas.bot_runner")

_STOP_EVENT = threading.Event()
_WORKER_THREAD: threading.Thread | None = None


def _now_utc() -> datetime:
    return datetime.utcnow()


def _resolve_session_market_type(session: BotSession, connector: Connector | None) -> str:
    explicit_market_type = None
    if getattr(session, "market_type", None):
        explicit_market_type = normalize_market_type(getattr(session, "market_type", None))

    connector_market_type = None
    if connector is not None:
        connector_market_type = resolve_runtime_market_type(connector)

    allowed_market_types = [
        normalize_market_type(item)
        for item in get_strategy_rule(getattr(session, "strategy_slug", "")).get("market_types", ["spot", "futures"])
    ]
    for candidate in (explicit_market_type, connector_market_type):
        if candidate and candidate in allowed_market_types:
            return candidate

    if len(allowed_market_types) == 1:
        return allowed_market_types[0]

    return explicit_market_type or connector_market_type or "spot"


def execute_due_bot_sessions(db, now: datetime | None = None) -> int:
    now = now or _now_utc()
    run_position_lifecycle(db)
    session_ids = [
        item[0]
        for item in db.query(BotSession.id)
        .filter(BotSession.is_active.is_(True))
        .order_by(BotSession.id.asc())
        .all()
    ]
    processed = 0

    for session_id in session_ids:
        processed += _process_due_bot_session(session_id=session_id, now=now)

    return processed


def _process_due_bot_session(*, session_id: int, now: datetime) -> int:
    db = SessionLocal()
    try:
        session = db.query(BotSession).filter(BotSession.id == session_id, BotSession.is_active.is_(True)).first()
        if not session:
            return 0

        if session.next_run_at and session.next_run_at > now:
            return 0

        connector = db.query(Connector).filter(Connector.id == session.connector_id).first()
        if not connector or not connector.is_enabled:
            session.last_status = "skipped"
            session.last_error = "Connector disabled or missing"
            session.last_run_at = now
            session.next_run_at = now + timedelta(minutes=max(session.interval_minutes, 1))
            commit_with_retry(db)
            return 1

        ensure_connector_market_type_state(connector, persist=True, db=db) if connector else "spot"
        session_market_type = normalize_market_type(getattr(session, "market_type", None))
        resolved_market_type = _resolve_session_market_type(session, connector)

        if session_market_type != resolved_market_type:
            session.market_type = resolved_market_type

        symbols = (session.symbols_json or {}).get("symbols", [])
        symbol_source_mode = str((session.symbols_json or {}).get("symbol_source_mode") or "manual")
        dynamic_symbol_limit = (session.symbols_json or {}).get("dynamic_symbol_limit")
        if not symbols:
            session.last_status = "skipped"
            session.last_error = "No symbols configured"
            session.last_run_at = now
            session.next_run_at = now + timedelta(minutes=max(session.interval_minutes, 1))
            commit_with_retry(db)
            return 1

        try:
            run_strategy(
                db=db,
                user_id=session.user_id,
                connector_ids=[session.connector_id],
                symbols=symbols,
                timeframe=session.timeframe,
                strategy_slug=session.strategy_slug,
                risk_per_trade=session.risk_per_trade,
                min_ml_probability=session.min_ml_probability,
                use_live_if_available=session.use_live_if_available,
                take_profit_mode=session.take_profit_mode,
                take_profit_value=session.take_profit_value,
                stop_loss_mode=session.stop_loss_mode,
                stop_loss_value=session.stop_loss_value,
                trailing_stop_mode=session.trailing_stop_mode,
                trailing_stop_value=session.trailing_stop_value,
                indicator_exit_enabled=session.indicator_exit_enabled,
                indicator_exit_rule=session.indicator_exit_rule,
                leverage_profile=session.leverage_profile,
                max_open_positions=max(int(session.max_open_positions or 1), 1),
                compound_growth_enabled=bool(session.compound_growth_enabled),
                atr_volatility_filter_enabled=bool(session.atr_volatility_filter_enabled),
                symbol_source_mode=symbol_source_mode,
                dynamic_symbol_limit=int(dynamic_symbol_limit) if dynamic_symbol_limit else None,
                run_source="bot",
                bot_session_id=session.id,
                market_type=resolved_market_type,
                trade_amount_mode=getattr(session, "trade_amount_mode", None),
                fixed_trade_amount_usd=getattr(session, "amount_per_trade", None),
                trade_balance_percent=getattr(session, "amount_percentage", None),
            )
            session.last_status = "ok"
            session.last_error = None
        except Exception as exc:
            rollback_safely(db)
            logger.exception("Bot session %s failed", session_id)
            session = db.query(BotSession).filter(BotSession.id == session_id).first()
            if not session:
                return 1
            session.last_status = "error"
            session.last_error = str(exc)

        session.last_run_at = now
        session.next_run_at = now + timedelta(minutes=max(session.interval_minutes, 1))
        commit_with_retry(db)
        return 1
    except Exception:
        rollback_safely(db)
        raise
    finally:
        db.close()


def _worker_loop() -> None:
    while not _STOP_EVENT.is_set():
        db = SessionLocal()
        try:
            execute_due_bot_sessions(db)
        except Exception:
            logger.exception("Background bot runner tick failed")
            rollback_safely(db)
        finally:
            db.close()
        _STOP_EVENT.wait(30)


def start_bot_worker() -> None:
    global _WORKER_THREAD
    if _WORKER_THREAD and _WORKER_THREAD.is_alive():
        return
    _STOP_EVENT.clear()
    _WORKER_THREAD = threading.Thread(target=_worker_loop, name="bot-runner", daemon=True)
    _WORKER_THREAD.start()


def stop_bot_worker(timeout: float = 5.0) -> None:
    global _WORKER_THREAD
    _STOP_EVENT.set()
    if _WORKER_THREAD and _WORKER_THREAD.is_alive():
        _WORKER_THREAD.join(timeout=timeout)
    _WORKER_THREAD = None
