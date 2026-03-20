import csv
import io
import json
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import OperationalError, PendingRollbackError
from sqlalchemy.orm.exc import ObjectDeletedError

from app.db import commit_with_retry, flush_with_retry, get_db, is_sqlite_locked_error, rollback_safely
from app.core import settings
from app.models import (
    BotSession,
    Connector,
    OpenPosition,
    PlanConfig,
    PlatformPolicy,
    PricingConfig,
    StrategyTemplate,
    TradeLog,
    TradeRun,
    User,
    UserPlatformGrant,
    UserStrategyControl,
)
from app.routers.deps import admin_user, current_user
from app.schemas import (
    AdminUserCreate,
    AdminGrantUpdate,
    AdminPlanConfigPayload,
    AdminPolicyUpdate,
    AdminPricingConfigUpdate,
    AdminStrategyControlUpdate,
    AdminUserUpdate,
    BotSessionCopyPayload,
    BotSessionCreate,
    BotSessionUpdate,
    ConnectorCreate,
    ConnectorUpdate,
    StrategyRequest,
    StrategyControlUpdate,
    StrategyTemplateApplyPayload,
    StrategyTemplateCreate,
    TradingViewWebhook,
)
from app.security import decrypt_payload, encrypt_payload, hash_password
from app.services.alerts import (
    TelegramDeliveryError,
    format_failure_message,
    format_user_failure_message,
    format_user_info_message,
    normalize_alert_locale,
    send_admin_user_alert_sync,
    send_telegram_alert_sync,
    send_user_telegram_test_alert,
)
from app.services.connector_state import (
    PLATFORM_MARKET_TYPES,
    ensure_connector_market_type_state,
    normalize_market_type,
    resolve_connector_market_type,
    resolve_runtime_market_type,
    sync_connector_config_market_type,
)
from app.services.connectors import get_client
from app.services.market import price_check
from app.services.policies import ensure_user_grants, get_user_grant, validate_connector_request
from app.services.pricing import estimate_monthly_cost
from app.services.position_lifecycle import trigger_kill_switch
from app.services.trading import activity_metrics, dashboard_data, run_strategy, sync_positions_with_exchange
from app.services.strategies import ALL_STRATEGIES as AVAILABLE_STRATEGIES, get_strategy_rule

router = APIRouter(prefix="/api", tags=["api"])
ROOT_ADMIN_EMAIL = (settings.admin_email or "davidksinc").strip().lower()
ALL_STRATEGIES = list(AVAILABLE_STRATEGIES)

logger = logging.getLogger("trading_saas.api")
BOT_SESSION_INITIAL_DELAY_SECONDS = 10
FUTURES_ONLY_CONNECTOR_CONFIG_KEYS = {
    "futures_margin_mode",
    "futures_position_mode",
    "futures_leverage",
    "leverage_profile",
}


def _extract_http_error_detail(exc: HTTPException) -> str:
    detail = getattr(exc, "detail", "")
    if isinstance(detail, (dict, list)):
        return json.dumps(detail, ensure_ascii=False)
    return str(detail)


def _safe_iso(value):
    return value.isoformat() if hasattr(value, "isoformat") and value else None


def _safe_json_object(value):
    return dict(value or {}) if isinstance(value, dict) else {}


def _safe_symbols(value) -> list[str]:
    if isinstance(value, dict):
        items = value.get("symbols") or []
    elif isinstance(value, list):
        items = value
    else:
        items = []
    return [str(item).strip() for item in items if str(item).strip()]


def _display_symbol(value: str | None) -> str:
    raw = str(value or "").strip().upper()
    if not raw:
        return "-"
    for suffix in ("/USDT", "USDT"):
        if raw.endswith(suffix):
            clean = raw[: -len(suffix)]
            return clean.rstrip("/") or raw
    return raw


def _translate_status_reason(reason_code: str | None) -> str:
    mapping = {
        "market_data_anomaly": "circuit_breaker: volatilidad_excesiva",
        "portfolio_heat_limit": "circuit_breaker: riesgo_global_alto",
        "symbol_concentration_limit": "circuit_breaker: riesgo_global_alto",
        "max_open_positions_reached": "circuit_breaker: overtrading",
        "max_open_positions": "circuit_breaker: overtrading",
        "trade_size_collapsed": "circuit_breaker: riesgo_global_alto",
        "balance_unavailable": "circuit_breaker: problemas_tecnicos",
        "missing_market_data": "circuit_breaker: problemas_tecnicos",
        "exchange_environment_not_ready": "circuit_breaker: problemas_tecnicos",
        "strategy_hold": "circuit_breaker: mercado_lateral_ruidoso",
        "low_confidence": "circuit_breaker: baja_calidad_de_senal",
        "short_disabled": "circuit_breaker: riesgo_global_alto",
        "spot_sell_without_inventory": "circuit_breaker: riesgo_global_alto",
        "invalid_symbol": "circuit_breaker: problemas_tecnicos",
        "last_candle_not_confirmed": "circuit_breaker: baja_calidad_de_senal",
        "rejected_invalid_quantity": "circuit_breaker: problemas_tecnicos",
        "skipped_min_qty": "circuit_breaker: problemas_tecnicos",
        "skipped_min_notional": "circuit_breaker: drawdown_reciente",
        "market_price_mismatch": "circuit_breaker: eventos_extremos_de_mercado",
        "suspicious_price_scale_detected": "circuit_breaker: eventos_extremos_de_mercado",
        "risk_engine_blocked": "circuit_breaker: riesgo_global_alto",
        "ok": "operativa_normal",
    }
    return mapping.get(str(reason_code or "ok"), f"circuit_breaker: {str(reason_code or 'ok')}")


REPORT_STATE_PRIORITY = [
    "volatilidad_excesiva",
    "drawdown_reciente",
    "overtrading",
    "mercado_lateral_ruidoso",
    "baja_calidad_de_senal",
    "riesgo_global_alto",
    "problemas_tecnicos",
    "eventos_extremos_de_mercado",
]


def _trade_run_reason_codes(run: TradeRun | None, parsed_note: dict | None = None) -> list[str]:
    if run is None:
        return []
    parsed = parsed_note if isinstance(parsed_note, dict) else {}
    summary = parsed.get("decision_summary") or {}
    raw_codes = summary.get("reason_codes") or []
    codes: list[str] = []
    for value in raw_codes:
        clean = str(value or "").strip()
        if clean and clean not in codes:
            codes.append(clean)
    primary = str(summary.get("primary_reason") or parsed.get("reason_code") or "").strip()
    if primary and primary not in codes:
        codes.append(primary)
    status = str(getattr(run, "status", "") or "").strip()
    if status.startswith("skipped_"):
        derived = status.removeprefix("skipped_").strip()
        if derived and derived not in codes:
            codes.append(derived)
    return codes


def _operational_states_from_reason_codes(reason_codes: list[str], notes: dict | None = None) -> list[str]:
    normalized_codes = [str(code or "").strip().lower() for code in reason_codes if str(code or "").strip()]
    parsed_notes = notes if isinstance(notes, dict) else {}
    states: list[str] = []
    code_to_state = {
        "market_data_anomaly": "volatilidad_excesiva",
        "skipped_circuit_breaker": "volatilidad_excesiva",
        "skipped_min_notional": "drawdown_reciente",
        "max_open_positions": "overtrading",
        "max_open_positions_reached": "overtrading",
        "strategy_hold": "mercado_lateral_ruidoso",
        "signal_hold": "mercado_lateral_ruidoso",
        "low_confidence": "baja_calidad_de_senal",
        "last_candle_not_confirmed": "baja_calidad_de_senal",
        "portfolio_heat_limit": "riesgo_global_alto",
        "symbol_concentration_limit": "riesgo_global_alto",
        "trade_size_collapsed": "riesgo_global_alto",
        "short_disabled": "riesgo_global_alto",
        "spot_sell_without_inventory": "riesgo_global_alto",
        "risk_engine_blocked": "riesgo_global_alto",
        "balance_unavailable": "problemas_tecnicos",
        "missing_market_data": "problemas_tecnicos",
        "exchange_environment_not_ready": "problemas_tecnicos",
        "invalid_symbol": "problemas_tecnicos",
        "rejected_invalid_quantity": "problemas_tecnicos",
        "skipped_min_qty": "problemas_tecnicos",
        "pretrade_rejected": "problemas_tecnicos",
        "exchange_rejected": "problemas_tecnicos",
        "market_price_mismatch": "eventos_extremos_de_mercado",
        "suspicious_price_scale_detected": "eventos_extremos_de_mercado",
    }
    for code in normalized_codes:
        state = code_to_state.get(code)
        if state and state not in states:
            states.append(state)

    if parsed_notes.get("circuit_breaker_triggered") and "volatilidad_excesiva" not in states:
        states.append("volatilidad_excesiva")
    if (parsed_notes.get("market_quality") or {}).get("anomalies") and "volatilidad_excesiva" not in states:
        anomalies = (parsed_notes.get("market_quality") or {}).get("anomalies") or {}
        issues = anomalies.get("issues") or []
        if anomalies.get("severity") not in {None, "", "ok"} or issues:
            states.append("volatilidad_excesiva")

    if not states:
        return ["operativa_normal"]
    ordered = [state for state in REPORT_STATE_PRIORITY if state in states]
    ordered.extend(state for state in states if state not in ordered)
    return ordered


def _trade_run_primary_reason(run: TradeRun | None) -> str:
    if run is None:
        return "ok"
    note = str(getattr(run, "notes", "") or "").strip()
    if not note or not note.startswith("{"):
        return "ok"
    try:
        parsed = json.loads(note)
    except json.JSONDecodeError:
        return "ok"
    summary = parsed.get("decision_summary") or {}
    return str(summary.get("primary_reason") or parsed.get("reason_code") or "ok")


def _trade_run_connector_snapshot(connector: Connector | None, parsed_note: dict | None = None) -> dict[str, str | int | None]:
    parsed = parsed_note if isinstance(parsed_note, dict) else {}
    snapshot = parsed.get("connector") or {}
    platform = connector.platform if connector else str(snapshot.get("platform") or "-")
    fallback_connector_id = getattr(connector, "id", None) if connector else snapshot.get("id")
    label = connector.label if connector and connector.label else str(snapshot.get("label") or f"Conector #{fallback_connector_id or '-'}")
    market_type = (
        ensure_connector_market_type_state(connector, persist=False) if connector
        else _normalize_market_type(
            snapshot.get("market_type")
            or parsed.get("market_type")
            or (parsed.get("execution_environment") or {}).get("market_type")
            or "spot"
        )
    )
    return {
        "connector_id": getattr(connector, "id", None) if connector else snapshot.get("id"),
        "connector_label": label or "-",
        "platform": platform or "-",
        "market_type": market_type or "spot",
    }


def _safe_float(value, fallback: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return fallback
    if result != result:
        return fallback
    return result


def _safe_int(value, fallback: int = 0) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return fallback
    return result


def _normalize_market_type(value: str | None) -> str:
    return normalize_market_type(value)


def _resolve_connector_market_type(*, platform: str, market_type: str | None = None, config: dict | None = None) -> str:
    return resolve_connector_market_type(platform=platform, market_type=market_type, config=config)


def _sync_connector_config_market_type(config: dict | None, market_type: str) -> dict:
    return sync_connector_config_market_type(config, market_type)


def _merge_connector_config(current: dict | None, incoming: dict | None, *, market_type: str) -> dict:
    merged = dict(current or {})
    for key, value in dict(incoming or {}).items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    if market_type != "futures":
        for key in FUTURES_ONLY_CONNECTOR_CONFIG_KEYS:
            merged.pop(key, None)
    return _sync_connector_config_market_type(merged, market_type)


def _connector_trade_amount_defaults(connector: Connector | None) -> dict[str, float | str | None]:
    config = _safe_json_object(getattr(connector, "config_json", {})) if connector is not None else {}
    mode = str(config.get("trade_amount_mode") or config.get("allocation_mode") or "fixed_usd").strip().lower()
    if mode in {"fixed", "fixed_amount"}:
        mode = "fixed_usd"
    if mode == "balance_percent":
        return {
            "trade_amount_mode": "balance_percent",
            "amount_per_trade": None,
            "amount_percentage": _safe_float(config.get("trade_balance_percent"), 10.0),
        }
    fixed_value = config.get("fixed_trade_amount_usd", config.get("allocation_value"))
    return {
        "trade_amount_mode": "fixed_usd",
        "amount_per_trade": _safe_float(fixed_value, 10.0),
        "amount_percentage": None,
    }


def _normalize_session_trade_amount_payload(
    *,
    mode: str | None,
    amount_per_trade: float | None,
    amount_percentage: float | None,
    current_mode: str | None = None,
    current_amount_per_trade: float | None = None,
    current_amount_percentage: float | None = None,
) -> dict[str, float | str | None]:
    resolved_mode = str(mode or current_mode or "inherit").lower()
    resolved_amount_per_trade = amount_per_trade if amount_per_trade is not None else current_amount_per_trade
    resolved_amount_percentage = amount_percentage if amount_percentage is not None else current_amount_percentage

    if resolved_mode == "inherit":
        return {
            "trade_amount_mode": "inherit",
            "amount_per_trade": None,
            "amount_percentage": None,
        }
    if resolved_mode == "fixed_usd":
        if resolved_amount_per_trade is None or _safe_float(resolved_amount_per_trade) <= 0:
            raise HTTPException(
                status_code=400,
                detail="PRECHECK_CONFIG_NOT_PERSISTED: amount_per_trade es obligatorio cuando trade_amount_mode=fixed_usd",
            )
        return {
            "trade_amount_mode": "fixed_usd",
            "amount_per_trade": _safe_float(resolved_amount_per_trade),
            "amount_percentage": None,
        }
    if resolved_mode == "balance_percent":
        if resolved_amount_percentage is None or _safe_float(resolved_amount_percentage) <= 0:
            raise HTTPException(
                status_code=400,
                detail="PRECHECK_CONFIG_NOT_PERSISTED: amount_percentage es obligatorio cuando trade_amount_mode=balance_percent",
            )
        return {
            "trade_amount_mode": "balance_percent",
            "amount_per_trade": None,
            "amount_percentage": _safe_float(resolved_amount_percentage),
        }
    raise HTTPException(status_code=400, detail=f"Unsupported trade_amount_mode: {resolved_mode}")


def _normalize_timeframe(value: str | None) -> str:
    clean = str(value or "5m").strip().lower()
    allowed = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"}
    return clean if clean in allowed else "5m"


def _interval_from_timeframe(timeframe: str, fallback: int | None = None) -> int:
    mapping = {
        "1m": 1,
        "3m": 3,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "1h": 60,
        "2h": 120,
        "4h": 240,
        "6h": 360,
        "8h": 480,
        "12h": 720,
        "1d": 1440,
    }
    normalized = _normalize_timeframe(timeframe)
    return int(fallback or mapping.get(normalized, 5))


def _alert_admin_failure(scope: str, detail: str) -> None:
    try:
        send_telegram_alert_sync(format_failure_message(scope, detail))
    except Exception:
        logger.exception("Could not notify admin failure for %s", scope)


def _raise_db_write_http_error(exc: Exception, *, action: str) -> None:
    detail = f"No se pudo {action} en este momento. Intenta de nuevo en unos segundos."
    if isinstance(exc, OperationalError) and is_sqlite_locked_error(exc):
        raise HTTPException(status_code=503, detail=f"{detail} La base de datos está ocupada temporalmente.")
    if isinstance(exc, PendingRollbackError):
        raise HTTPException(status_code=503, detail=f"{detail} La transacción previa quedó inválida y ya fue revertida.")
    if isinstance(exc, (ObjectDeletedError,)):
        raise HTTPException(status_code=409, detail=f"{detail} El registro cambió mientras se procesaba la solicitud.")
    raise


def _notify_user_info(user: User | None, *, title: str, detail: str, connector_label: str | None = None,
                      platform: str | None = None, symbol: str | None = None,
                      connection_status: str | None = None, markets_connected: str | None = None,
                      candles_reviewed: int | None = None, trend_summary: str | None = None) -> None:
    if user is None:
        return
    try:
        message = format_user_info_message(
            locale=getattr(user, "alert_language", "es"),
            title=title,
            detail=detail,
            connector_label=connector_label,
            platform=platform,
            symbol=symbol,
            connection_status=connection_status,
            markets_connected=markets_connected,
            candles_reviewed=candles_reviewed,
            trend_summary=trend_summary,
        )
        send_admin_user_alert_sync(user, message, scope="user-info")
    except Exception:
        logger.exception("Could not send user info notification")


def _validate_strategy_connectors(db, *, user_id: int, connector_ids: list[int], strategy_slug: str) -> list[Connector]:
    connectors = db.query(Connector).filter(Connector.user_id == user_id, Connector.id.in_(connector_ids)).all()
    if len(connectors) != len(set(connector_ids)):
        raise HTTPException(status_code=404, detail="One or more connectors were not found")

    strategy_rule = get_strategy_rule(strategy_slug)
    allowed_market_types = {normalize_market_type(item) for item in strategy_rule.get("market_types", ["spot", "futures"])}
    incompatible = []
    for connector in connectors:
        connector_market_type = ensure_connector_market_type_state(connector, persist=False)
        if connector_market_type not in allowed_market_types:
            incompatible.append(f"{connector.label} ({connector_market_type})")

    if incompatible:
        raise HTTPException(
            status_code=400,
            detail=f"La estrategia {strategy_slug} no es compatible con: {', '.join(incompatible)}",
        )
    return connectors


def _resolve_trade_amount_settings(user: User, payload, connector: Connector | None = None) -> dict[str, float | str | None]:
    mode = str(getattr(payload, "trade_amount_mode", None) or "inherit").lower()
    if mode == "inherit":
        return _connector_trade_amount_defaults(connector)
    return {
        "trade_amount_mode": mode,
        "amount_per_trade": _safe_float(getattr(payload, "amount_per_trade", None), 0.0) or None,
        "amount_percentage": _safe_float(getattr(payload, "amount_percentage", None), 0.0) or None,
    }


def _estimate_trade_investment(trade: TradeLog, user: User | None) -> float:
    quantity = _safe_float(getattr(trade, "quantity", 0.0), 0.0)
    price = _safe_float(getattr(trade, "price", 0.0), 0.0)
    notional = quantity * price
    if notional > 0:
        return notional
    if user is not None and getattr(user, "trade_amount_mode", "fixed_usd") == "balance_percent":
        return _safe_float(getattr(user, "trade_balance_percent", 0.0), 0.0)
    return _safe_float(getattr(user, "fixed_trade_amount_usd", 0.0), 0.0) if user is not None else 0.0


def _is_root_admin(user: User) -> bool:
    # IMPORTANT: root-admin identity must rely on immutable identity only.
    # user.name is editable via /api/me and cannot be used for privilege checks.
    return (user.email or "").strip().lower() == ROOT_ADMIN_EMAIL


def _ensure_strategy_control(db, user_id: int) -> UserStrategyControl:
    control = db.query(UserStrategyControl).filter(UserStrategyControl.user_id == user_id).first()
    if not control:
        control = UserStrategyControl(user_id=user_id, managed_by_admin=False, allowed_strategies_json={"items": ALL_STRATEGIES})
        db.add(control)
        db.commit()
        db.refresh(control)
    allowed = (control.allowed_strategies_json or {}).get("items")
    if not allowed or (not control.managed_by_admin and set(allowed) != set(ALL_STRATEGIES)):
        control.allowed_strategies_json = {"items": ALL_STRATEGIES}
        db.commit()
    return control

@router.get("/me")
def me(user=Depends(current_user), db=Depends(get_db)):
    ensure_user_grants(db, user)
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "phone": user.phone,
        "is_admin": user.is_admin,
        "alert_language": normalize_alert_locale(user.alert_language),
        "admin_alerts_enabled": bool((settings.telegram_admin_bot_token or "").strip() and (settings.telegram_admin_chat_id or "").strip()),
        "telegram_alerts_enabled": bool(getattr(user, "telegram_alerts_enabled", False)),
        "has_telegram_bot_key": bool((decrypt_payload(user.telegram_bot_token_encrypted).get("value") or "").strip()),
        "telegram_bot_key": (decrypt_payload(user.telegram_bot_token_encrypted).get("value") or "").strip() or None,
        "telegram_chat_id": (decrypt_payload(user.telegram_chat_id_encrypted).get("value") or "").strip() or None,
        "trade_amount_mode": user.trade_amount_mode or "fixed_usd",
        "fixed_trade_amount_usd": float(user.fixed_trade_amount_usd or 10),
        "trade_balance_percent": float(user.trade_balance_percent or 10),
    }


@router.put("/me")
def me_update(payload: dict, db=Depends(get_db), user=Depends(current_user)):
    next_name = payload.get("name")
    if next_name is not None:
        clean_name = str(next_name).strip()
        if len(clean_name) < 2 or len(clean_name) > 255:
            raise HTTPException(status_code=400, detail="Name must be between 2 and 255 characters")
        user.name = clean_name

    next_phone = payload.get("phone")
    if next_phone is not None:
        clean_phone = str(next_phone).strip()
        if clean_phone and (len(clean_phone) < 7 or len(clean_phone) > 40):
            raise HTTPException(status_code=400, detail="Phone must be between 7 and 40 characters")
        user.phone = clean_phone or None

    next_language = payload.get("alert_language")
    if next_language is not None:
        user.alert_language = normalize_alert_locale(str(next_language))

    if "telegram_alerts_enabled" in payload:
        user.telegram_alerts_enabled = bool(payload.get("telegram_alerts_enabled"))
    if "telegram_bot_key" in payload:
        bot_key = str(payload.get("telegram_bot_key") or "").strip()
        user.telegram_bot_token_encrypted = encrypt_payload({"value": bot_key}) if bot_key else None
    if "telegram_chat_id" in payload:
        chat_id = str(payload.get("telegram_chat_id") or "").strip()
        user.telegram_chat_id_encrypted = encrypt_payload({"value": chat_id}) if chat_id else None

    next_trade_mode = payload.get("trade_amount_mode")
    if next_trade_mode is not None:
        mode = str(next_trade_mode).strip().lower()
        if mode not in {"fixed_usd", "balance_percent"}:
            raise HTTPException(status_code=400, detail="trade_amount_mode must be fixed_usd or balance_percent")
        user.trade_amount_mode = mode

    next_fixed_amount = payload.get("fixed_trade_amount_usd")
    if next_fixed_amount is not None:
        try:
            amount = float(next_fixed_amount)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="fixed_trade_amount_usd must be numeric")
        if amount < 10:
            raise HTTPException(status_code=400, detail="El monto fijo mínimo para Binance es 10 USD")
        user.fixed_trade_amount_usd = amount

    next_balance_percent = payload.get("trade_balance_percent")
    if next_balance_percent is not None:
        try:
            percent = float(next_balance_percent)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="trade_balance_percent must be numeric")
        if percent <= 0 or percent > 100:
            raise HTTPException(status_code=400, detail="trade_balance_percent debe estar entre 0 y 100")
        user.trade_balance_percent = percent

    db.commit()
    return {
        "ok": True,
        "id": user.id,
        "name": user.name,
        "phone": user.phone,
        "alert_language": normalize_alert_locale(user.alert_language),
        "admin_alerts_enabled": bool((settings.telegram_admin_bot_token or "").strip() and (settings.telegram_admin_chat_id or "").strip()),
        "telegram_alerts_enabled": bool(getattr(user, "telegram_alerts_enabled", False)),
        "has_telegram_bot_key": bool((decrypt_payload(user.telegram_bot_token_encrypted).get("value") or "").strip()),
        "telegram_bot_key": (decrypt_payload(user.telegram_bot_token_encrypted).get("value") or "").strip() or None,
        "telegram_chat_id": (decrypt_payload(user.telegram_chat_id_encrypted).get("value") or "").strip() or None,
        "trade_amount_mode": user.trade_amount_mode,
        "fixed_trade_amount_usd": float(user.fixed_trade_amount_usd or 10),
        "trade_balance_percent": float(user.trade_balance_percent or 10),
    }


@router.api_route("/me/telegram/test", methods=["GET", "POST"])
def me_telegram_test(db=Depends(get_db), user=Depends(current_user)):
    _ = db
    try:
        ok = send_user_telegram_test_alert(user, raise_on_error=True)
    except TelegramDeliveryError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    if not ok:
        raise HTTPException(status_code=502, detail="No se pudo enviar la prueba al Telegram configurado para este usuario")
    return {"ok": True, "message": "Mensaje de prueba enviado al Telegram del usuario"}


@router.get("/platform-metadata")
def platform_metadata(db=Depends(get_db), user=Depends(current_user)):
    ensure_user_grants(db, user)
    policies = db.query(PlatformPolicy).order_by(PlatformPolicy.category, PlatformPolicy.display_name).all()
    grants = {
        grant.platform: grant for grant in db.query(UserPlatformGrant).filter(UserPlatformGrant.user_id == user.id).all()
    }
    return {
        "platforms": [{
            "platform": p.platform,
            "display_name": p.display_name,
            "category": p.category,
            "is_enabled_global": p.is_enabled_global,
            "allow_manual_symbols": p.allow_manual_symbols,
            "top_symbols": (p.top_symbols_json or {}).get("symbols", []),
            "allowed_symbols": (p.allowed_symbols_json or {}).get("symbols", []),
            "guide": p.guide_json,
            "grant": {
                "is_enabled": grants[p.platform].is_enabled if p.platform in grants else False,
                "max_symbols": grants[p.platform].max_symbols if p.platform in grants else 0,
                "max_daily_movements": grants[p.platform].max_daily_movements if p.platform in grants else 0,
                "notes": grants[p.platform].notes if p.platform in grants else None,
            }
        } for p in policies]
    }


@router.get("/connectors")
def list_connectors(db=Depends(get_db), user=Depends(current_user)):
    connectors = db.query(Connector).filter(Connector.user_id == user.id).order_by(Connector.created_at.desc()).all()
    payload = []
    serialization_errors = []
    for connector in connectors:
        try:
            resolved_market_type = ensure_connector_market_type_state(connector, persist=True, db=db)
            payload.append({
                "id": connector.id,
                "platform": connector.platform,
                "label": connector.label,
                "mode": connector.mode,
                "market_type": resolved_market_type,
                "is_enabled": bool(connector.is_enabled),
                "symbols": _safe_symbols(getattr(connector, "symbols_json", {})),
                "config": _safe_json_object(getattr(connector, "config_json", {})),
                "has_saved_credentials": bool((decrypt_payload(getattr(connector, "encrypted_secret_blob", None)) or {}).keys()),
                "created_at": _safe_iso(getattr(connector, "created_at", None)),
            })
        except Exception as exc:
            detail = f"user_id={user.id} connector_id={getattr(connector, 'id', '-')}: {exc}"
            logger.exception("Failed serializing connector: %s", detail)
            serialization_errors.append(detail)
            payload.append({
                "id": getattr(connector, "id", None),
                "platform": getattr(connector, "platform", "-"),
                "label": getattr(connector, "label", "Conector inválido"),
                "mode": getattr(connector, "mode", "paper"),
                "market_type": _normalize_market_type(getattr(connector, "market_type", "spot") or "spot"),
                "is_enabled": bool(getattr(connector, "is_enabled", False)),
                "symbols": [],
                "config": {},
                "has_saved_credentials": False,
                "created_at": _safe_iso(getattr(connector, "created_at", None)),
            })

    if serialization_errors:
        _alert_admin_failure("API /api/connectors serialization", " | ".join(serialization_errors)[:1500])
    db.commit()
    return payload


@router.post("/connectors")
def create_connector(payload: ConnectorCreate, db=Depends(get_db), user: User = Depends(current_user)):
    target_user_id = payload.user_id or user.id
    if target_user_id != user.id:
        admin_user(user)
    target_user = db.query(User).filter(User.id == target_user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")
    ensure_user_grants(db, target_user)
    market_type = _resolve_connector_market_type(
        platform=payload.platform,
        market_type=payload.market_type,
        config=payload.config,
    )
    validate_connector_request(db, target_user, payload.platform, payload.symbols)
    connector = Connector(
        user_id=target_user.id,
        platform=payload.platform,
        label=payload.label,
        mode=payload.mode,
        market_type=market_type,
        symbols_json={"symbols": payload.symbols},
        config_json=_merge_connector_config({}, payload.config, market_type=market_type),
        encrypted_secret_blob=encrypt_payload(payload.secrets),
    )
    ensure_connector_market_type_state(connector)
    db.add(connector)
    db.commit()
    db.refresh(connector)
    _notify_user_info(
        target_user,
        title="Conector creado",
        detail=f"Se creó el conector {connector.label} en modo {connector.mode}, mercado {connector.market_type} y {len(payload.symbols)} símbolos base.",
        connector_label=connector.label,
        platform=connector.platform,
    )
    return {"ok": True, "connector_id": connector.id}


@router.put("/connectors/{connector_id}")
def update_connector(connector_id: int, payload: ConnectorUpdate, db=Depends(get_db), user: User = Depends(current_user)):
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    if connector.user_id != user.id:
        admin_user(user)

    next_symbols = payload.symbols if payload.symbols is not None else connector.symbols_json.get("symbols", [])
    owner = db.query(User).filter(User.id == connector.user_id).first()
    if not owner:
        raise HTTPException(status_code=400, detail="Connector owner not found")
    validate_connector_request(db, owner, connector.platform, next_symbols, connector_id=connector.id)

    if payload.label is not None:
        connector.label = payload.label
    if payload.mode is not None:
        connector.mode = payload.mode
    next_config = _merge_connector_config(connector.config_json, payload.config, market_type=connector.market_type)
    connector.market_type = _resolve_connector_market_type(
        platform=connector.platform,
        market_type=payload.market_type or getattr(connector, "market_type", None),
        config=next_config,
    )
    if payload.symbols is not None:
        connector.symbols_json = {"symbols": payload.symbols}
    connector.config_json = _merge_connector_config(connector.config_json, payload.config, market_type=connector.market_type)
    if payload.secrets is not None:
        connector.encrypted_secret_blob = encrypt_payload(payload.secrets)
    if payload.is_enabled is not None:
        connector.is_enabled = payload.is_enabled
    db.commit()
    _notify_user_info(
        owner,
        title="Conector actualizado",
        detail=f"{connector.label} quedó en modo {connector.mode}, mercado {connector.market_type} y estado {'activo' if connector.is_enabled else 'inactivo'}.",
        connector_label=connector.label,
        platform=connector.platform,
    )
    return {"ok": True}


@router.delete("/connectors/{connector_id}")
def delete_connector(connector_id: int, db=Depends(get_db), user: User = Depends(current_user)):
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    if connector.user_id != user.id:
        admin_user(user)
    owner = db.query(User).filter(User.id == connector.user_id).first()
    detail = f"Se eliminó el conector {connector.label} ({connector.platform})."
    db.delete(connector)
    db.commit()
    if owner:
        _notify_user_info(owner, title="Conector eliminado", detail=detail)
    return {"ok": True}


@router.post("/connectors/{connector_id}/test")
def test_connector(connector_id: int, db=Depends(get_db), user=Depends(current_user)):
    connector = db.query(Connector).filter(Connector.id == connector_id, Connector.user_id == user.id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    ensure_connector_market_type_state(connector, persist=True, db=db)
    client = get_client(connector)
    try:
        data = client.test_connection()
        raw_text = json.dumps(data, ensure_ascii=False) if isinstance(data, (dict, list)) else str(data or "")
        _notify_user_info(
            user,
            title="Prueba de conector exitosa",
            detail=(
                f"{connector.label} respondió correctamente a la prueba de conexión. "
                f"Mercado conectado: {connector.market_type}. "
                f"Símbolos base: {len(_safe_symbols(getattr(connector, 'symbols_json', {})))}. "
                f"Respuesta resumida: {raw_text[:220] or 'ok'}"
            ),
            connector_label=connector.label,
            platform=connector.platform,
            connection_status="ok",
            markets_connected=f"{connector.platform}/{connector.market_type}",
            candles_reviewed=0,
            trend_summary="Conector listo para monitoreo y ejecución",
        )
        return {"status": "ok", "message": "Connection test completed", "raw": data}
    except Exception as exc:
        send_admin_user_alert_sync(
            user,
            format_user_failure_message(
                locale=user.alert_language,
                scope="connector_test",
                detail=str(exc),
                connector_label=connector.label,
                platform=connector.platform,
            ),
            scope="connector-test-error",
        )
        return {"status": "error", "message": str(exc), "raw": {"platform": connector.platform}}


@router.put("/connectors/{connector_id}/credentials")
def update_connector_credentials(connector_id: int, payload: ConnectorUpdate, db=Depends(get_db), user=Depends(current_user)):
    connector = db.query(Connector).filter(Connector.id == connector_id, Connector.user_id == user.id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    if payload.secrets is not None:
        connector.encrypted_secret_blob = encrypt_payload(payload.secrets)

    if payload.config is not None:
        connector.config_json = _merge_connector_config(
            connector.config_json,
            payload.config,
            market_type=normalize_market_type(getattr(connector, "market_type", None) or "spot"),
        )
    ensure_connector_market_type_state(connector, persist=True, db=db)

    db.commit()
    _notify_user_info(
        user,
        title="Credenciales actualizadas",
        detail=f"Se actualizaron credenciales/configuración sensible para {connector.label}.",
        connector_label=connector.label,
        platform=connector.platform,
    )
    return {"ok": True}


@router.post("/strategies/run")
def run_strategy_endpoint(payload: StrategyRequest, db=Depends(get_db), user=Depends(current_user)):
    control = _ensure_strategy_control(db, user.id)
    allowed = (control.allowed_strategies_json or {}).get("items", ALL_STRATEGIES)
    if control.managed_by_admin and payload.strategy_slug not in allowed:
        raise HTTPException(status_code=403, detail="Strategy is managed by admin for this user")
    risk_value = payload.risk_per_trade / 100 if payload.risk_per_trade > 1 else payload.risk_per_trade
    ml_value = payload.min_ml_probability / 100 if payload.min_ml_probability > 1 else payload.min_ml_probability
    connectors = _validate_strategy_connectors(db, user_id=user.id, connector_ids=payload.connector_ids, strategy_slug=payload.strategy_slug)
    trade_amount_settings = _resolve_trade_amount_settings(user, payload, connectors[0] if connectors else None)

    result = run_strategy(
        db=db,
        user_id=user.id,
        connector_ids=payload.connector_ids,
        symbols=payload.symbols,
        timeframe=payload.timeframe,
        strategy_slug=payload.strategy_slug,
        risk_per_trade=risk_value,
        min_ml_probability=ml_value,
        use_live_if_available=payload.use_live_if_available,
        take_profit_mode=payload.take_profit_mode,
        take_profit_value=payload.take_profit_value,
        stop_loss_mode=payload.stop_loss_mode,
        stop_loss_value=payload.stop_loss_value,
        trailing_stop_mode=payload.trailing_stop_mode,
        trailing_stop_value=payload.trailing_stop_value,
        indicator_exit_enabled=payload.indicator_exit_enabled,
        indicator_exit_rule=payload.indicator_exit_rule,
        leverage_profile=payload.leverage_profile,
        max_open_positions=payload.max_open_positions,
        compound_growth_enabled=payload.compound_growth_enabled,
        atr_volatility_filter_enabled=payload.atr_volatility_filter_enabled,
        symbol_source_mode=payload.symbol_source_mode,
        dynamic_symbol_limit=payload.dynamic_symbol_limit,
        run_source="manual",
        market_type=payload.market_type,
        trade_amount_mode=trade_amount_settings["trade_amount_mode"],
        fixed_trade_amount_usd=trade_amount_settings["amount_per_trade"],
        trade_balance_percent=trade_amount_settings["amount_percentage"],
    )
    active_connectors = db.query(Connector).filter(
        Connector.id.in_(payload.connector_ids),
        Connector.user_id == user.id,
    ).all()
    status_counts: dict[str, int] = {}
    for item in result:
        status = str(item.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    connected_markets = ", ".join(
        f"{connector.label} ({connector.platform}/{ensure_connector_market_type_state(connector, persist=True, db=db)})"
        for connector in active_connectors
    ) or "sin conectores resueltos"
    estimated_candles = max(len(payload.symbols), 1) * 220
    trend_summary = (
        f"Estrategia {payload.strategy_slug} en {payload.timeframe}. "
        f"Sesgo monitorizado sobre {len(payload.symbols)} mercado(s) con modo {payload.symbol_source_mode}."
    )
    _notify_user_info(
        user,
        title="Estrategia ejecutada manualmente",
        detail=(
            f"{payload.strategy_slug} sobre {len(payload.symbols)} símbolos. "
            f"Mercados conectados: {connected_markets}. "
            f"Velas revisadas estimadas: {estimated_candles}. "
            f"Tendencias/escenario: {trend_summary}. "
            f"Resultado: " + ", ".join(f"{status}={count}" for status, count in sorted(status_counts.items()))
        ),
        symbol=", ".join(payload.symbols[:3]) if payload.symbols else None,
        connection_status="ok",
        markets_connected=connected_markets,
        candles_reviewed=estimated_candles,
        trend_summary=trend_summary,
    )
    return {"ok": True, "results": result}


@router.get("/strategy-control")
def get_strategy_control(db=Depends(get_db), user=Depends(current_user)):
    control = _ensure_strategy_control(db, user.id)
    return {
        "managed_by_admin": control.managed_by_admin,
        "allowed_strategies": (control.allowed_strategies_json or {}).get("items", ALL_STRATEGIES),
        "all_strategies": ALL_STRATEGIES,
    }


@router.put("/strategy-control")
def update_strategy_control(payload: StrategyControlUpdate, db=Depends(get_db), user=Depends(current_user)):
    control = _ensure_strategy_control(db, user.id)
    if control.managed_by_admin:
        raise HTTPException(status_code=403, detail="Strategy selection is managed by admin for this user")

    allowed = [s for s in payload.allowed_strategies if s in ALL_STRATEGIES]
    control.allowed_strategies_json = {"items": allowed or ALL_STRATEGIES}
    db.add(control)
    db.commit()
    return {
        "ok": True,
        "managed_by_admin": control.managed_by_admin,
        "allowed_strategies": (control.allowed_strategies_json or {}).get("items", ALL_STRATEGIES),
        "all_strategies": ALL_STRATEGIES,
    }


@router.get("/bot-sessions")
def list_bot_sessions(db=Depends(get_db), user=Depends(current_user)):
    sessions = db.query(BotSession).outerjoin(Connector, BotSession.connector_id == Connector.id).filter(
        BotSession.user_id == user.id
    ).order_by(BotSession.created_at.desc()).all()
    payload = []
    serialization_errors = []
    for session in sessions:
        try:
            connector = session.connector
            symbols = _safe_symbols(getattr(session, "symbols_json", {}))
            config = _safe_json_object(getattr(connector, "config_json", {})) if connector else {}
            session_mode = str(getattr(session, "trade_amount_mode", None) or "inherit").lower()
            connector_defaults = _connector_trade_amount_defaults(connector)
            effective_mode = str(connector_defaults["trade_amount_mode"] or "fixed_usd") if session_mode == "inherit" else session_mode
            if effective_mode == "balance_percent":
                capital = _safe_float(
                    getattr(session, "amount_percentage", None)
                    or connector_defaults.get("amount_percentage")
                    or 0
                )
            else:
                capital = _safe_float(
                    getattr(session, "amount_per_trade", None)
                    or connector_defaults.get("amount_per_trade")
                    or 0
                )
            session_market_type = normalize_market_type(getattr(session, "market_type", None))
            payload.append({
                "id": session.id,
                "connector_id": session.connector_id,
                "connector_label": connector.label if connector else "-",
                "platform": connector.platform if connector else "-",
                "mode": connector.mode if connector else "-",
                "market_type": session_market_type or (connector.market_type if connector else "spot"),
                "strategy_slug": session.strategy_slug,
                "timeframe": session.timeframe,
                "symbols": symbols,
                "symbol_source_mode": str((session.symbols_json or {}).get("symbol_source_mode") or "manual"),
                "dynamic_symbol_limit": int((session.symbols_json or {}).get("dynamic_symbol_limit") or len(symbols) or 1),
                "interval_minutes": session.interval_minutes,
                "risk_per_trade": session.risk_per_trade,
                "min_ml_probability": session.min_ml_probability,
                "take_profit_mode": session.take_profit_mode,
                "take_profit_value": session.take_profit_value,
                "stop_loss_mode": session.stop_loss_mode,
                "stop_loss_value": session.stop_loss_value,
                "trailing_stop_mode": session.trailing_stop_mode,
                "trailing_stop_value": session.trailing_stop_value,
                "indicator_exit_enabled": session.indicator_exit_enabled,
                "indicator_exit_rule": session.indicator_exit_rule,
                "leverage_profile": getattr(session, "leverage_profile", "none"),
                "max_open_positions": max(int(getattr(session, "max_open_positions", 1) or 1), 1),
                "compound_growth_enabled": bool(getattr(session, "compound_growth_enabled", False)),
                "atr_volatility_filter_enabled": bool(getattr(session, "atr_volatility_filter_enabled", True)),
                "is_active": session.is_active,
                "last_run_at": _safe_iso(session.last_run_at),
                "next_run_at": _safe_iso(session.next_run_at),
                "last_status": session.last_status,
                "last_error": session.last_error,
                "capital_per_operation": capital,
                "capital_display_unit": "%" if effective_mode == "balance_percent" else "USDT",
                "capital_currency": "USDT",
                "trade_amount_mode": effective_mode,
                "configured_trade_amount_mode": session_mode,
                "configured_amount_per_trade": _safe_float(getattr(session, "amount_per_trade", None), 0.0) or None,
                "configured_amount_percentage": _safe_float(getattr(session, "amount_percentage", None), 0.0) or None,
                "created_at": _safe_iso(session.created_at),
            })
        except Exception as exc:
            detail = f"user_id={user.id} session_id={getattr(session, 'id', '-')}: {exc}"
            logger.exception("Failed serializing bot session: %s", detail)
            serialization_errors.append(detail)
            payload.append({
                "id": getattr(session, "id", None),
                "connector_id": getattr(session, "connector_id", None),
                "connector_label": "-",
                "platform": "-",
                "mode": "-",
                "market_type": "spot",
                "strategy_slug": getattr(session, "strategy_slug", "-"),
                "timeframe": getattr(session, "timeframe", "5m"),
                "symbols": [],
                "symbol_source_mode": "manual",
                "dynamic_symbol_limit": 1,
                "interval_minutes": getattr(session, "interval_minutes", 5),
                "risk_per_trade": _safe_float(getattr(session, "risk_per_trade", 0.0)),
                "min_ml_probability": _safe_float(getattr(session, "min_ml_probability", 0.0)),
                "take_profit_mode": "percent",
                "take_profit_value": 1.5,
                "stop_loss_mode": "percent",
                "stop_loss_value": 1.0,
                "trailing_stop_mode": "percent",
                "trailing_stop_value": 0.8,
                "indicator_exit_enabled": False,
                "indicator_exit_rule": "macd_cross",
                "leverage_profile": "none",
                "max_open_positions": 1,
                "compound_growth_enabled": False,
                "atr_volatility_filter_enabled": True,
                "is_active": bool(getattr(session, "is_active", False)),
                "last_run_at": _safe_iso(getattr(session, "last_run_at", None)),
                "next_run_at": _safe_iso(getattr(session, "next_run_at", None)),
                "last_status": "error",
                "last_error": "No se pudo serializar esta sesión. Revisa configuración y logs.",
                "capital_per_operation": 0.0,
                "capital_display_unit": "USDT",
                "capital_currency": "USDT",
                "created_at": _safe_iso(getattr(session, "created_at", None)),
            })

    if serialization_errors:
        _alert_admin_failure(
            "API /api/bot-sessions serialization",
            " | ".join(serialization_errors)[:1500],
        )
    return payload


@router.post("/bot-sessions")
def create_bot_session(payload: BotSessionCreate, db=Depends(get_db), user=Depends(current_user)):
    try:
        control = _ensure_strategy_control(db, user.id)
        allowed = (control.allowed_strategies_json or {}).get("items", ALL_STRATEGIES)
        if control.managed_by_admin and payload.strategy_slug not in allowed:
            raise HTTPException(status_code=403, detail="Strategy is managed by admin for this user")

        connector = db.query(Connector).filter(
            Connector.id == payload.connector_id,
            Connector.user_id == user.id,
            Connector.is_enabled.is_(True),
        ).first()
        if not connector:
            raise HTTPException(status_code=404, detail="Enabled connector not found")

        _validate_strategy_connectors(db, user_id=user.id, connector_ids=[connector.id], strategy_slug=payload.strategy_slug)

        risk_value = payload.risk_per_trade / 100 if payload.risk_per_trade > 1 else payload.risk_per_trade
        ml_value = payload.min_ml_probability / 100 if payload.min_ml_probability > 1 else payload.min_ml_probability
        trade_amount_settings = _resolve_trade_amount_settings(user, payload, connector)
        normalized_amounts = _normalize_session_trade_amount_payload(
            mode=str(trade_amount_settings["trade_amount_mode"]),
            amount_per_trade=_safe_float(trade_amount_settings["amount_per_trade"], 0.0) or None,
            amount_percentage=_safe_float(trade_amount_settings["amount_percentage"], 0.0) or None,
        )
        resolved_market_type = resolve_runtime_market_type(connector, requested_market_type=payload.market_type)

        normalized_timeframe = _normalize_timeframe(payload.timeframe)
        session = BotSession(
            user_id=user.id,
            connector_id=connector.id,
            market_type=resolved_market_type,
            strategy_slug=payload.strategy_slug,
            timeframe=normalized_timeframe,
            symbols_json={
                "symbols": payload.symbols,
                "symbol_source_mode": payload.symbol_source_mode,
                "dynamic_symbol_limit": payload.dynamic_symbol_limit,
            },
            interval_minutes=_interval_from_timeframe(normalized_timeframe, payload.interval_minutes),
            risk_per_trade=risk_value,
            trade_amount_mode=str(normalized_amounts["trade_amount_mode"]),
            amount_per_trade=normalized_amounts["amount_per_trade"],
            amount_percentage=normalized_amounts["amount_percentage"],
            min_ml_probability=ml_value,
            use_live_if_available=payload.use_live_if_available,
            take_profit_mode=payload.take_profit_mode,
            take_profit_value=payload.take_profit_value,
            stop_loss_mode=payload.stop_loss_mode,
            stop_loss_value=payload.stop_loss_value,
            trailing_stop_mode=payload.trailing_stop_mode,
            trailing_stop_value=payload.trailing_stop_value,
            indicator_exit_enabled=payload.indicator_exit_enabled,
            indicator_exit_rule=payload.indicator_exit_rule,
            leverage_profile=payload.leverage_profile,
            max_open_positions=payload.max_open_positions,
            compound_growth_enabled=payload.compound_growth_enabled,
            atr_volatility_filter_enabled=payload.atr_volatility_filter_enabled,
            is_active=True,
            last_status="queued",
            next_run_at=datetime.utcnow() + timedelta(seconds=BOT_SESSION_INITIAL_DELAY_SECONDS),
        )
        db.add(session)
        flush_with_retry(db)
        session_id = session.id
        strategy_slug = session.strategy_slug
        timeframe = session.timeframe
        commit_with_retry(db)
    except HTTPException:
        rollback_safely(db)
        raise
    except Exception as exc:
        rollback_safely(db)
        _raise_db_write_http_error(exc, action="crear la sesión automática")

    _notify_user_info(
        user,
        title="Bot 24/7 activado",
        detail=f"Sesión #{session_id} creada con estrategia {strategy_slug} en timeframe {timeframe}. La primera corrida quedó en cola para ejecutarse automáticamente.",
        connector_label=connector.label,
        platform=connector.platform,
    )

    return {"ok": True, "session_id": session_id}


@router.put("/bot-sessions/{session_id}")
def update_bot_session(session_id: int, payload: BotSessionUpdate, db=Depends(get_db), user=Depends(current_user)):
    try:
        session = db.query(BotSession).filter(BotSession.id == session_id, BotSession.user_id == user.id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Bot session not found")

        control = _ensure_strategy_control(db, user.id)
        allowed = (control.allowed_strategies_json or {}).get("items", ALL_STRATEGIES)

        if payload.is_active is not None:
            session.is_active = payload.is_active
        if payload.symbols is not None:
            current_symbols_json = _safe_json_object(getattr(session, "symbols_json", {}))
            current_symbols_json["symbols"] = payload.symbols
            session.symbols_json = current_symbols_json
        if payload.symbol_source_mode is not None:
            current_symbols_json = _safe_json_object(getattr(session, "symbols_json", {}))
            current_symbols_json["symbol_source_mode"] = payload.symbol_source_mode
            session.symbols_json = current_symbols_json
        if payload.dynamic_symbol_limit is not None:
            current_symbols_json = _safe_json_object(getattr(session, "symbols_json", {}))
            current_symbols_json["dynamic_symbol_limit"] = payload.dynamic_symbol_limit
            session.symbols_json = current_symbols_json
        if payload.strategy_slug is not None:
            if control.managed_by_admin and payload.strategy_slug not in allowed:
                raise HTTPException(status_code=403, detail="Strategy is managed by admin for this user")
            _validate_strategy_connectors(db, user_id=user.id, connector_ids=[session.connector_id], strategy_slug=payload.strategy_slug)
            session.strategy_slug = payload.strategy_slug
        connector = db.query(Connector).filter(Connector.id == session.connector_id).first()
        if payload.market_type is not None and connector is not None:
            session.market_type = resolve_runtime_market_type(connector, requested_market_type=payload.market_type)
        if payload.timeframe is not None:
            normalized_timeframe = _normalize_timeframe(payload.timeframe)
            session.timeframe = normalized_timeframe
            session.interval_minutes = _interval_from_timeframe(normalized_timeframe, payload.interval_minutes or session.interval_minutes)
        elif payload.interval_minutes is not None:
            session.interval_minutes = payload.interval_minutes

        if payload.risk_per_trade is not None:
            session.risk_per_trade = payload.risk_per_trade / 100 if payload.risk_per_trade > 1 else payload.risk_per_trade
        if payload.trade_amount_mode is not None or payload.amount_per_trade is not None or payload.amount_percentage is not None:
            normalized_amounts = _normalize_session_trade_amount_payload(
                mode=payload.trade_amount_mode,
                amount_per_trade=payload.amount_per_trade,
                amount_percentage=payload.amount_percentage,
                current_mode=getattr(session, "trade_amount_mode", "inherit"),
                current_amount_per_trade=getattr(session, "amount_per_trade", None),
                current_amount_percentage=getattr(session, "amount_percentage", None),
            )
            session.trade_amount_mode = str(normalized_amounts["trade_amount_mode"])
            session.amount_per_trade = normalized_amounts["amount_per_trade"]
            session.amount_percentage = normalized_amounts["amount_percentage"]
        if payload.min_ml_probability is not None:
            session.min_ml_probability = payload.min_ml_probability / 100 if payload.min_ml_probability > 1 else payload.min_ml_probability
        if payload.use_live_if_available is not None:
            session.use_live_if_available = payload.use_live_if_available
        if payload.take_profit_mode is not None:
            session.take_profit_mode = payload.take_profit_mode
        if payload.take_profit_value is not None:
            session.take_profit_value = payload.take_profit_value
        if payload.stop_loss_mode is not None:
            session.stop_loss_mode = payload.stop_loss_mode
        if payload.stop_loss_value is not None:
            session.stop_loss_value = payload.stop_loss_value
        if payload.trailing_stop_mode is not None:
            session.trailing_stop_mode = payload.trailing_stop_mode
        if payload.trailing_stop_value is not None:
            session.trailing_stop_value = payload.trailing_stop_value
        if payload.indicator_exit_enabled is not None:
            session.indicator_exit_enabled = payload.indicator_exit_enabled
        if payload.indicator_exit_rule is not None:
            session.indicator_exit_rule = payload.indicator_exit_rule
        if payload.leverage_profile is not None:
            session.leverage_profile = payload.leverage_profile
        if payload.max_open_positions is not None:
            session.max_open_positions = payload.max_open_positions
        if payload.compound_growth_enabled is not None:
            session.compound_growth_enabled = payload.compound_growth_enabled
        if payload.atr_volatility_filter_enabled is not None:
            session.atr_volatility_filter_enabled = payload.atr_volatility_filter_enabled

        commit_with_retry(db)
        connector = connector or db.query(Connector).filter(Connector.id == session.connector_id).first()
    except HTTPException:
        rollback_safely(db)
        raise
    except Exception as exc:
        rollback_safely(db)
        _raise_db_write_http_error(exc, action="actualizar la sesión automática")

    _notify_user_info(
        user,
        title="Bot actualizado",
        detail=f"Sesión #{session.id} ahora está {'activa' if session.is_active else 'pausada'} con estrategia {session.strategy_slug} y timeframe {session.timeframe}.",
        connector_label=connector.label if connector else None,
        platform=connector.platform if connector else None,
    )
    return {"ok": True}


@router.delete("/bot-sessions/{session_id}")
def delete_bot_session(session_id: int, db=Depends(get_db), user=Depends(current_user)):
    try:
        session = db.query(BotSession).filter(BotSession.id == session_id, BotSession.user_id == user.id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Bot session not found")
        connector = db.query(Connector).filter(Connector.id == session.connector_id).first()
        detail = f"Se eliminó la sesión #{session.id} con estrategia {session.strategy_slug}."
        session.is_active = False
        commit_with_retry(db)
        db.delete(session)
        commit_with_retry(db)
    except HTTPException:
        rollback_safely(db)
        raise
    except Exception as exc:
        rollback_safely(db)
        _raise_db_write_http_error(exc, action="eliminar la sesión automática")

    _notify_user_info(
        user,
        title="Bot eliminado",
        detail=detail,
        connector_label=connector.label if connector else None,
        platform=connector.platform if connector else None,
    )
    return {"ok": True}


@router.post("/bot-sessions/{session_id}/copy")
def copy_bot_session(session_id: int, payload: BotSessionCopyPayload, db=Depends(get_db), user=Depends(current_user)):
    try:
        source = db.query(BotSession).filter(BotSession.id == session_id, BotSession.user_id == user.id).first()
        if not source:
            raise HTTPException(status_code=404, detail="Bot session not found")

        target_connector_id = payload.connector_id or source.connector_id
        connector = db.query(Connector).filter(Connector.id == target_connector_id, Connector.user_id == user.id, Connector.is_enabled.is_(True)).first()
        if not connector:
            raise HTTPException(status_code=404, detail="Enabled connector not found")

        source_symbols_json = _safe_json_object(getattr(source, "symbols_json", {}))
        _validate_strategy_connectors(db, user_id=user.id, connector_ids=[connector.id], strategy_slug=source.strategy_slug)
        cloned = BotSession(
            user_id=user.id,
            connector_id=connector.id,
            market_type=resolve_runtime_market_type(connector, requested_market_type=getattr(source, "market_type", None)),
            strategy_slug=source.strategy_slug,
            timeframe=source.timeframe,
            symbols_json={
                **source_symbols_json,
                "symbols": payload.symbols if payload.symbols is not None else (source_symbols_json.get("symbols", [])),
            },
            interval_minutes=source.interval_minutes,
            risk_per_trade=source.risk_per_trade,
            trade_amount_mode=getattr(source, "trade_amount_mode", "inherit"),
            amount_per_trade=getattr(source, "amount_per_trade", None),
            amount_percentage=getattr(source, "amount_percentage", None),
            min_ml_probability=source.min_ml_probability,
            use_live_if_available=source.use_live_if_available,
            take_profit_mode=source.take_profit_mode,
            take_profit_value=source.take_profit_value,
            stop_loss_mode=source.stop_loss_mode,
            stop_loss_value=source.stop_loss_value,
            trailing_stop_mode=source.trailing_stop_mode,
            trailing_stop_value=source.trailing_stop_value,
            indicator_exit_enabled=source.indicator_exit_enabled,
            indicator_exit_rule=source.indicator_exit_rule,
            leverage_profile=getattr(source, "leverage_profile", "none"),
            max_open_positions=max(int(getattr(source, "max_open_positions", 1) or 1), 1),
            compound_growth_enabled=bool(getattr(source, "compound_growth_enabled", False)),
            atr_volatility_filter_enabled=bool(getattr(source, "atr_volatility_filter_enabled", True)),
            is_active=bool(source.is_active),
            last_status="cloned",
            next_run_at=datetime.utcnow() + timedelta(seconds=BOT_SESSION_INITIAL_DELAY_SECONDS) if bool(source.is_active) else None,
        )
        db.add(cloned)
        flush_with_retry(db)
        cloned_id = cloned.id
        commit_with_retry(db)
    except HTTPException:
        rollback_safely(db)
        raise
    except Exception as exc:
        rollback_safely(db)
        _raise_db_write_http_error(exc, action="duplicar la sesión automática")

    _notify_user_info(
        user,
        title="Bot clonado",
        detail=f"Se clonó la sesión #{source.id} hacia la nueva sesión #{cloned_id}.",
        connector_label=connector.label,
        platform=connector.platform,
    )
    return {"ok": True, "session_id": cloned_id}


@router.get("/connectors/{connector_id}/symbols-catalog")
def connector_symbols_catalog(connector_id: int, db=Depends(get_db), user=Depends(current_user)):
    connector = db.query(Connector).filter(
        Connector.id == connector_id,
        Connector.user_id == user.id,
    ).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    policy = db.query(PlatformPolicy).filter(PlatformPolicy.platform == connector.platform).first()
    symbols = sorted({
        *(_safe_symbols(getattr(connector, "symbols_json", {}))),
        *((policy.top_symbols_json or {}).get("symbols", []) if policy else []),
        *((policy.allowed_symbols_json or {}).get("symbols", []) if policy else []),
    })
    source = "configured_universe"

    if connector.platform in {"binance", "bybit", "okx"}:
        try:
            client = get_client(connector)
            exchange = client.build_exchange()
            markets = exchange.load_markets()
            market_type = str(getattr(connector, "market_type", "spot") or "spot").lower()
            symbols = sorted(
                symbol
                for symbol, market in (markets or {}).items()
                if market.get("active", True)
                and (
                    (market_type == "spot" and market.get("spot"))
                    or (market_type == "futures" and (market.get("future") or market.get("swap")))
                    or market_type not in {"spot", "futures"}
                )
            )
            if market_type in {"spot", "futures"}:
                symbols = [symbol for symbol in symbols if symbol.endswith("/USDT")] or symbols
            source = "exchange_markets"
        except Exception as exc:
            source = f"configured_universe_fallback:{exc}"

    payload = symbols[:2000]
    return {
        "connector_id": connector.id,
        "platform": connector.platform,
        "market_type": connector.market_type,
        "symbols": payload,
        "count": len(payload),
        "source": source,
    }


@router.get("/execution-logs/download")
def download_execution_logs(limit: int = 500, db=Depends(get_db), user=Depends(current_user)):
    target = min(max(limit, 1), 2000)
    runs = db.query(TradeRun).filter(TradeRun.user_id == user.id).order_by(TradeRun.created_at.desc()).limit(target).all()

    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow([
        "id",
        "created_at",
        "connector_id",
        "platform",
        "market_type",
        "connector_label",
        "symbol",
        "display_symbol",
        "timeframe",
        "signal",
        "status",
        "status_reason",
        "operational_states",
        "ml_probability",
        "quantity",
        "notes_json",
    ])
    for run in runs:
        note = run.notes or ""
        try:
            parsed_note = json.loads(note) if note else {}
        except json.JSONDecodeError:
            parsed_note = {"raw_notes": note}
        connector = db.query(Connector).filter(Connector.id == run.connector_id).first()
        reason_codes = _trade_run_reason_codes(run, parsed_note)
        reason_code = reason_codes[0] if reason_codes else "ok"
        connector_meta = _trade_run_connector_snapshot(connector, parsed_note)
        writer.writerow([
            run.id,
            run.created_at.isoformat() if run.created_at else "",
            run.connector_id,
            connector_meta["platform"],
            connector_meta["market_type"],
            connector_meta["connector_label"],
            run.symbol,
            _display_symbol(run.symbol),
            run.timeframe,
            run.signal,
            run.status,
            _translate_status_reason(reason_code),
            "|".join(_operational_states_from_reason_codes(reason_codes, parsed_note)),
            run.ml_probability,
            run.quantity,
            run.notes or "",
        ])
    stream.seek(0)
    filename = f"execution_logs_user_{user.id}.csv"
    return StreamingResponse(iter([stream.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.get("/strategy-templates")
def list_strategy_templates(db=Depends(get_db), user=Depends(current_user)):
    mine = db.query(StrategyTemplate).filter(StrategyTemplate.user_id == user.id).order_by(StrategyTemplate.created_at.desc()).all()
    public_templates = db.query(StrategyTemplate).filter(StrategyTemplate.is_public.is_(True), StrategyTemplate.user_id != user.id).order_by(StrategyTemplate.created_at.desc()).limit(200).all()
    rows = []
    for item in [*mine, *public_templates]:
        rows.append({
            "id": item.id,
            "user_id": item.user_id,
            "name": item.name,
            "description": item.description,
            "is_public": bool(item.is_public),
            "source_template_id": item.source_template_id,
            "config": item.config_json or {},
            "created_at": _safe_iso(item.created_at),
            "owned": item.user_id == user.id,
        })
    return rows


@router.post("/strategy-templates")
def create_strategy_template(payload: StrategyTemplateCreate, db=Depends(get_db), user=Depends(current_user)):
    config = payload.config or {}
    if payload.source_bot_session_id:
        source = db.query(BotSession).filter(BotSession.id == payload.source_bot_session_id, BotSession.user_id == user.id).first()
        if not source:
            raise HTTPException(status_code=404, detail="Source bot session not found")
        config = {
            "strategy_slug": source.strategy_slug,
            "market_type": getattr(source, "market_type", None),
            "timeframe": source.timeframe,
            "risk_per_trade": source.risk_per_trade,
            "trade_amount_mode": getattr(source, "trade_amount_mode", "inherit"),
            "amount_per_trade": getattr(source, "amount_per_trade", None),
            "amount_percentage": getattr(source, "amount_percentage", None),
            "min_ml_probability": source.min_ml_probability,
            "use_live_if_available": source.use_live_if_available,
            "take_profit_mode": source.take_profit_mode,
            "take_profit_value": source.take_profit_value,
            "stop_loss_mode": source.stop_loss_mode,
            "stop_loss_value": source.stop_loss_value,
            "trailing_stop_mode": source.trailing_stop_mode,
            "trailing_stop_value": source.trailing_stop_value,
            "indicator_exit_enabled": source.indicator_exit_enabled,
            "indicator_exit_rule": source.indicator_exit_rule,
            "interval_minutes": source.interval_minutes,
            "symbols": ((source.symbols_json or {}).get("symbols") or []),
            "connector_id": source.connector_id,
        }

    tpl = StrategyTemplate(
        user_id=user.id,
        name=payload.name,
        description=payload.description,
        is_public=payload.is_public,
        config_json=config,
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return {"ok": True, "template_id": tpl.id}


@router.post("/strategy-templates/{template_id}/copy")
def copy_strategy_template(template_id: int, db=Depends(get_db), user=Depends(current_user)):
    source = db.query(StrategyTemplate).filter(StrategyTemplate.id == template_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Template not found")
    if source.user_id != user.id and not source.is_public:
        raise HTTPException(status_code=403, detail="Template is private")

    clone = StrategyTemplate(
        user_id=user.id,
        name=f"{source.name} (copy)",
        description=source.description,
        is_public=False,
        source_template_id=source.id,
        config_json=source.config_json or {},
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)
    return {"ok": True, "template_id": clone.id}


@router.post("/strategy-templates/{template_id}/apply")
def apply_strategy_template(template_id: int, payload: StrategyTemplateApplyPayload, db=Depends(get_db), user=Depends(current_user)):
    template = db.query(StrategyTemplate).filter(StrategyTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if template.user_id != user.id and not template.is_public:
        raise HTTPException(status_code=403, detail="Template is private")

    connector = db.query(Connector).filter(Connector.id == payload.connector_id, Connector.user_id == user.id, Connector.is_enabled.is_(True)).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Enabled connector not found")

    cfg = template.config_json or {}
    _validate_strategy_connectors(db, user_id=user.id, connector_ids=[connector.id], strategy_slug=cfg.get("strategy_slug", "ema_rsi"))
    session = BotSession(
        user_id=user.id,
        connector_id=connector.id,
        market_type=resolve_runtime_market_type(connector, requested_market_type=cfg.get("market_type")),
        strategy_slug=cfg.get("strategy_slug", "ema_rsi"),
        timeframe=cfg.get("timeframe", "5m"),
        symbols_json={"symbols": payload.symbols},
        interval_minutes=int(cfg.get("interval_minutes", _interval_from_timeframe(cfg.get("timeframe", "5m"), 5))),
        risk_per_trade=float(cfg.get("risk_per_trade", 0.03)),
        trade_amount_mode=cfg.get("trade_amount_mode", "inherit"),
        amount_per_trade=cfg.get("amount_per_trade"),
        amount_percentage=cfg.get("amount_percentage"),
        min_ml_probability=float(cfg.get("min_ml_probability", 0.58)),
        use_live_if_available=bool(cfg.get("use_live_if_available", False)),
        take_profit_mode=cfg.get("take_profit_mode", "percent"),
        take_profit_value=float(cfg.get("take_profit_value", 1.8)),
        stop_loss_mode=cfg.get("stop_loss_mode", "percent"),
        stop_loss_value=float(cfg.get("stop_loss_value", 1.1)),
        trailing_stop_mode=cfg.get("trailing_stop_mode", "percent"),
        trailing_stop_value=float(cfg.get("trailing_stop_value", 0.9)),
        indicator_exit_enabled=bool(cfg.get("indicator_exit_enabled", False)),
        indicator_exit_rule=cfg.get("indicator_exit_rule", "macd_cross"),
        leverage_profile=cfg.get("leverage_profile", "none"),
        max_open_positions=max(int(cfg.get("max_open_positions", 1) or 1), 1),
        compound_growth_enabled=bool(cfg.get("compound_growth_enabled", False)),
        atr_volatility_filter_enabled=bool(cfg.get("atr_volatility_filter_enabled", True)),
        is_active=payload.is_active,
        last_status="from_template",
        next_run_at=datetime.utcnow() + timedelta(seconds=BOT_SESSION_INITIAL_DELAY_SECONDS) if payload.is_active else None,
    )
    db.add(session)
    db.flush()
    session_id = session.id
    db.commit()
    return {"ok": True, "session_id": session_id}


@router.get("/activity/performance")
def activity_performance(db=Depends(get_db), user=Depends(current_user)):
    try:
        return activity_metrics(db, user.id)
    except Exception as exc:
        detail = f"user_id={user.id}: {exc}"
        logger.exception("Activity metrics build failed: %s", detail)
        _alert_admin_failure("API /api/activity/performance", detail)
        return {
            "equity_curve": [],
            "drawdown_curve": [],
            "monthly_returns": [],
            "yearly_returns": [],
            "summary": {
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "profit_factor": 0.0,
                "win_rate": 0.0,
                "total_trades": 0,
            },
        }


@router.get("/dashboard")
def dashboard(db=Depends(get_db), user=Depends(current_user)):
    try:
        data = dashboard_data(db, user.id)
    except Exception as exc:
        detail = f"user_id={user.id}: {exc}"
        logger.exception("Dashboard data build failed: %s", detail)
        _alert_admin_failure("API /api/dashboard", detail)
        return {
            "total_connectors": 0,
            "enabled_connectors": 0,
            "total_trades": 0,
            "realized_pnl": 0.0,
            "total_invested": 0.0,
            "realized_pnl_percent": 0.0,
            "winning_trades": 0,
            "losing_trades": 0,
            "platforms": {},
            "statuses": {},
            "latest_trades": [],
            "limits": [],
            "risk_summary": {
                "open_positions": 0,
                "open_notional": 0.0,
                "estimated_open_risk": 0.0,
                "largest_position_pct": 0.0,
                "daily_realized_pnl": 0.0,
                "rolling_drawdown_pct": 0.0,
                "degraded_data_runs": 0,
                "kill_switch_armed": False,
                "health_score": 100.0,
                "alerts": [],
                "suggestions": [],
                "by_symbol": [],
                "guardrails": {},
            },
            "insights": [],
        }
    safe_trades = []
    for trade in data.get("latest_trades", []):
        try:
            safe_trades.append({
                "id": trade.id,
                "platform": trade.platform,
                "symbol": trade.symbol,
                "side": trade.side,
                "quantity": trade.quantity,
                "price": trade.price,
                "status": trade.status,
                "pnl": trade.pnl,
                "created_at": _safe_iso(getattr(trade, "created_at", None)),
            })
        except Exception:
            continue
    return {**data, "latest_trades": safe_trades}


@router.get("/exchange-symbol-rules")
def exchange_symbol_rules(connector_id: int, symbols: str | None = None, db=Depends(get_db), user=Depends(current_user)):
    connector = db.query(Connector).filter(Connector.id == connector_id, Connector.user_id == user.id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    if connector.platform not in {"binance", "bybit", "okx"}:
        raise HTTPException(status_code=400, detail="Exchange symbol rules are only available for Binance/Bybit/OKX")

    selected_symbols = [item.strip().upper() for item in (symbols or "").split(",") if item.strip()]
    if not selected_symbols:
        selected_symbols = [str(item).upper() for item in ((connector.symbols_json or {}).get("symbols") or [])]

    client = get_client(connector)
    if not hasattr(client, "min_requirements"):
        raise HTTPException(status_code=400, detail="Connector does not provide symbol filters")

    rows = [client.min_requirements(symbol) for symbol in selected_symbols]
    return {
        "connector_id": connector.id,
        "connector_label": connector.label,
        "platform": connector.platform,
        "rows": rows,
    }


@router.get("/debug/price-check")
def debug_price_check(connector_id: int, symbol: str, timeframe: str = "1h", db=Depends(get_db), user=Depends(current_user)):
    connector = db.query(Connector).filter(Connector.id == connector_id, Connector.user_id == user.id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    return price_check(connector=connector, symbol=symbol, timeframe=timeframe)


@router.post("/connectors/{connector_id}/reconcile")
def reconcile_connector(connector_id: int, payload: dict | None = None, db=Depends(get_db), user=Depends(current_user)):
    connector = db.query(Connector).filter(Connector.id == connector_id, Connector.user_id == user.id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    raw_symbols = (payload or {}).get("symbols") or (connector.symbols_json or {}).get("symbols") or []
    symbols = [str(item).strip() for item in raw_symbols if str(item).strip()]
    result = sync_positions_with_exchange(db, connector, symbols)
    _notify_user_info(
        user,
        title="Reconciliación ejecutada",
        detail=f"{connector.label}: {len(result.get('resolved', []))} símbolos reconciliados y {len(result.get('orphaned', []))} posiciones huérfanas detectadas.",
        connector_label=connector.label,
        platform=connector.platform,
    )
    return result


@router.post("/risk/kill-switch")
def risk_kill_switch(payload: dict | None = None, db=Depends(get_db), user=Depends(current_user)):
    connector_ids = [int(item) for item in ((payload or {}).get("connector_ids") or [])]
    result = trigger_kill_switch(db, connector_ids=connector_ids or None, reason="manual")
    _notify_user_info(
        user,
        title="Kill switch ejecutado",
        detail=f"Se intentó cerrar {len(result.get('closed', [])) + len(result.get('failed', []))} posiciones abiertas.",
    )
    return result


@router.get("/market/top-strength")
async def market_top_strength(limit: int = 10, platform: str | None = None, symbols: str | None = None, range: str = "day", user=Depends(current_user)):
    _ = user
    import httpx

    target = min(max(limit, 1), 20)
    wanted = [s.strip().upper().replace("/", "") for s in (symbols or "").split(",") if s.strip()]
    active_platform = (platform or "").lower()
    crypto_platforms = {"binance", "bybit", "okx"}

    if active_platform in crypto_platforms or (not active_platform and not wanted):
        url = "https://api.binance.com/api/v3/ticker/24hr"
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()

        ranked_source = [item for item in payload if str(item.get("symbol", "")).endswith("USDT")]
        if wanted:
            wanted_set = set(wanted)
            ranked_source = [item for item in ranked_source if str(item.get("symbol", "")).upper() in wanted_set]
        
        metric_by_range = {
            "day": "priceChangePercent",
            "week": "priceChangePercent",
            "month": "priceChangePercent",
        }
        metric = metric_by_range.get((range or "day").lower(), "priceChangePercent")
        ranked = sorted(ranked_source, key=lambda item: float(item.get(metric, 0) or 0), reverse=True)[:target]
        return [{
            "symbol": item.get("symbol"),
            "price": float(item.get("lastPrice", 0) or 0),
            "change_percent": float(item.get("priceChangePercent", 0) or 0),
            "volume": float(item.get("quoteVolume", 0) or 0),
        } for item in ranked]

    fallback = wanted[:target] if wanted else ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "US30", "NAS100", "BTCUSD", "ETHUSD", "AUDUSD", "USDCAD"][:target]
    rows = []
    for index, symbol in enumerate(fallback, start=1):
        strength = max(0.5, 9.5 - (index - 1) * 0.7)
        change = round(strength if index % 2 else -strength * 0.6, 2)
        rows.append({
            "symbol": symbol,
            "price": 0.0,
            "change_percent": change,
            "volume": 0.0,
        })
    return rows


@router.get("/trades")
def list_trades(db=Depends(get_db), user=Depends(current_user)):
    trades = db.query(TradeLog).filter(TradeLog.user_id == user.id).order_by(TradeLog.created_at.desc()).limit(200).all()
    return [{
        "id": t.id,
        "platform": t.platform,
        "symbol": t.symbol,
        "side": t.side,
        "quantity": t.quantity,
        "price": t.price,
        "status": t.status,
        "pnl": t.pnl,
        "investment_amount": round(_estimate_trade_investment(t, user), 8),
        "created_at": t.created_at.isoformat(),
        "meta": t.meta_json,
    } for t in trades]


@router.get("/execution-logs")
def execution_logs(limit: int = 200, db=Depends(get_db), user=Depends(current_user)):
    target = min(max(limit, 1), 500)
    runs = db.query(TradeRun).filter(TradeRun.user_id == user.id).order_by(TradeRun.created_at.desc()).limit(target).all()
    payload = []
    for run in runs:
        note = run.notes or ""
        try:
            parsed_note = json.loads(note) if note else {}
        except json.JSONDecodeError:
            parsed_note = {"raw_notes": note}
        connector = db.query(Connector).filter(Connector.id == run.connector_id).first()
        reason_codes = _trade_run_reason_codes(run, parsed_note)
        reason_code = reason_codes[0] if reason_codes else "ok"
        connector_meta = _trade_run_connector_snapshot(connector, parsed_note)
        payload.append({
            "id": run.id,
            "connector_id": connector_meta["connector_id"] or run.connector_id,
            "connector_label": connector_meta["connector_label"],
            "platform": connector_meta["platform"],
            "market_type": connector_meta["market_type"],
            "symbol": run.symbol,
            "display_symbol": _display_symbol(run.symbol),
            "strategy_slug": run.strategy_slug,
            "timeframe": run.timeframe,
            "signal": run.signal,
            "status": run.status,
            "status_reason_code": reason_code,
            "status_reason": _translate_status_reason(reason_code),
            "reason_codes": reason_codes,
            "operational_states": _operational_states_from_reason_codes(reason_codes, parsed_note),
            "ml_probability": run.ml_probability,
            "quantity": run.quantity,
            "created_at": run.created_at.isoformat(),
            "notes": parsed_note,
            "candle": parsed_note.get("candle") or (parsed_note.get("scanner") or {}).get("candle"),
        })
    return payload


@router.post("/webhooks/tradingview")
def tradingview_webhook(payload: TradingViewWebhook, db=Depends(get_db)):
    connector = db.query(Connector).filter(Connector.id == payload.connector_id, Connector.platform == "tradingview").first()
    if not connector:
        raise HTTPException(status_code=404, detail="TradingView connector not found")

    configured_passphrase = (connector.config_json or {}).get("passphrase")
    if configured_passphrase and payload.passphrase != configured_passphrase:
        raise HTTPException(status_code=403, detail="Invalid webhook passphrase")

    status = "signal-received"
    meta = {"strategy_slug": payload.strategy_slug, "extra": payload.extra}

    if payload.target_connector_id:
        target = db.query(Connector).filter(
            Connector.id == payload.target_connector_id,
            Connector.user_id == connector.user_id,
            Connector.is_enabled.is_(True),
        ).first()
        if not target:
            raise HTTPException(status_code=404, detail="Target connector not found")
        client = get_client(target)
        qty = payload.quantity or float((target.config_json or {}).get("default_quantity", 1.0))
        result = client.execute_market(symbol=payload.symbol, side=payload.side, quantity=qty, price_hint=payload.price)
        status = result.status
        meta["forwarded_to"] = {"connector_id": target.id, "platform": target.platform, "message": result.message}
        meta["execution_raw"] = result.raw

    db.add(TradeLog(
        user_id=connector.user_id,
        connector_id=connector.id,
        platform="tradingview",
        symbol=payload.symbol,
        side=payload.side,
        quantity=payload.quantity or 1.0,
        price=payload.price,
        status=status,
        pnl=0.0,
        meta_json=meta,
    ))
    db.commit()
    owner = db.query(User).filter(User.id == connector.user_id).first()
    if owner:
        _notify_user_info(
            owner,
            title="Webhook recibido",
            detail=f"TradingView envió una señal {payload.side} y quedó con estado {status}.",
            connector_label=connector.label,
            platform=connector.platform,
            symbol=payload.symbol,
        )
    return {"ok": True, "message": "Webhook processed", "status": status}


@router.get("/heartbeat")
def connector_heartbeat(db=Depends(get_db), user=Depends(current_user)):
    connectors = db.query(Connector).filter(Connector.user_id == user.id, Connector.is_enabled.is_(True)).all()
    checks = []
    checked_at = datetime.utcnow().isoformat()
    for connector in connectors:
        try:
            client = get_client(connector)
            raw = client.test_connection()
            checks.append({
                "id": connector.id,
                "label": connector.label,
                "platform": connector.platform,
                "market_type": ensure_connector_market_type_state(connector, persist=True, db=db),
                "ok": True,
                "message": "Conector validado",
                "raw": raw,
            })
        except Exception as exc:
            checks.append({
                "id": connector.id,
                "label": connector.label,
                "platform": connector.platform,
                "market_type": ensure_connector_market_type_state(connector, persist=True, db=db),
                "ok": False,
                "message": str(exc),
                "raw": None,
            })
            send_admin_user_alert_sync(
                user,
                format_user_failure_message(
                    locale=user.alert_language,
                    scope="heartbeat",
                    detail=str(exc),
                    connector_label=connector.label,
                    platform=connector.platform,
                ),
                scope="heartbeat-error",
            )
    return {
        "ok": all(item["ok"] for item in checks) if checks else True,
        "total": len(checks),
        "checked_at": checked_at,
        "checks": checks,
    }


@router.get("/public/plans-config")
def public_plans_config(db=Depends(get_db)):
    pricing = db.query(PricingConfig).first()
    if not pricing:
        raise HTTPException(status_code=404, detail="Pricing config missing")
    plans = db.query(PlanConfig).filter(PlanConfig.is_active.is_(True)).order_by(PlanConfig.sort_order.asc(), PlanConfig.id.asc()).all()
    quote = estimate_monthly_cost(pricing, apps=3, symbols=15, daily_movements=20)
    return {
        "pricing": {
            "base_commission_usd": pricing.base_commission_usd,
            "cost_per_app_usd": pricing.cost_per_app_usd,
            "cost_per_symbol_usd": pricing.cost_per_symbol_usd,
            "cost_per_movement_usd": pricing.cost_per_movement_usd,
            "cost_per_gb_ram_usd": pricing.cost_per_gb_ram_usd,
            "cost_per_gb_disk_usd": pricing.cost_per_gb_disk_usd,
            "suggested_ram_per_app_gb": pricing.suggested_ram_per_app_gb,
            "suggested_disk_per_app_gb": pricing.suggested_disk_per_app_gb,
        },
        "plans": [{
            "id": plan.id,
            "name": plan.name,
            "description": plan.description,
            "apps": plan.apps,
            "symbols": plan.symbols,
            "daily_movements": plan.daily_movements,
            "monthly_price_usd": plan.monthly_price_usd,
            "is_custom": plan.is_custom,
        } for plan in plans],
        "example_quote": quote,
    }


@router.post("/public/estimate")
def public_estimate(payload: dict, db=Depends(get_db)):
    pricing = db.query(PricingConfig).first()
    if not pricing:
        raise HTTPException(status_code=404, detail="Pricing config missing")
    apps = max(int(payload.get("apps", 1)), 0)
    symbols = max(int(payload.get("symbols", 1)), 0)
    daily_movements = max(int(payload.get("daily_movements", 1)), 0)
    return estimate_monthly_cost(pricing, apps=apps, symbols=symbols, daily_movements=daily_movements)


@router.get("/admin/users")
def admin_list_users(db=Depends(get_db), _: User = Depends(admin_user)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [{
        "id": u.id,
        "email": u.email,
        "name": u.name,
        "is_active": u.is_active,
        "is_admin": u.is_admin,
        "created_at": u.created_at.isoformat(),
    } for u in users]


@router.put("/admin/users/{user_id}")
def admin_update_user(user_id: int, payload: AdminUserUpdate, db=Depends(get_db), actor: User = Depends(admin_user)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if _is_root_admin(user):
        raise HTTPException(status_code=403, detail=f"{ROOT_ADMIN_EMAIL} is hierarchical and cannot be modified")

    if payload.is_admin is not None and not _is_root_admin(actor):
        raise HTTPException(status_code=403, detail=f"Only {ROOT_ADMIN_EMAIL} can assign or remove admin role")

    if payload.email is not None:
        next_email = payload.email.strip().lower()
        if not next_email:
            raise HTTPException(status_code=400, detail="Email cannot be empty")
        exists = db.query(User).filter(User.email == next_email, User.id != user.id).first()
        if exists:
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email = next_email
    if payload.name is not None:
        user.name = payload.name.strip()
    if payload.phone is not None:
        user.phone = (payload.phone or "").strip() or None
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.is_admin is not None:
        user.is_admin = payload.is_admin

    db.commit()
    _notify_user_info(
        user,
        title="Perfil actualizado por administración",
        detail=f"Tu cuenta quedó como {'activa' if user.is_active else 'inactiva'} y rol {'admin' if user.is_admin else 'usuario'}.",
    )
    return {"ok": True}


@router.delete("/admin/users/{user_id}")
def admin_delete_user(user_id: int, db=Depends(get_db), actor: User = Depends(admin_user)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == actor.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    if _is_root_admin(user):
        raise HTTPException(status_code=403, detail=f"{ROOT_ADMIN_EMAIL} is hierarchical and cannot be deleted")

    detail = f"Cuenta eliminada por admin. Usuario={user.name} email={user.email}"
    send_admin_user_alert_sync(user, format_failure_message("Admin User Delete", detail), scope="admin-user-delete")
    db.delete(user)
    db.commit()
    return {"ok": True}


@router.get("/admin/users/{user_id}/profile")
def admin_user_profile(user_id: int, db=Depends(get_db), _: User = Depends(admin_user)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    ensure_user_grants(db, user)
    connectors = db.query(Connector).filter(Connector.user_id == user_id).order_by(Connector.created_at.desc()).all()
    grants = db.query(UserPlatformGrant).filter(UserPlatformGrant.user_id == user_id).all()
    grants_by_platform = {g.platform: g for g in grants}
    strategy_control = _ensure_strategy_control(db, user.id)
    recent_runs = db.query(TradeRun).filter(TradeRun.user_id == user_id).order_by(TradeRun.created_at.desc()).limit(8).all()
    recent_sessions = db.query(BotSession).filter(BotSession.user_id == user_id).order_by(BotSession.updated_at.desc()).limit(6).all()

    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "phone": user.phone,
            "is_admin": user.is_admin,
            "is_active": user.is_active,
            "is_root": _is_root_admin(user),
            "alert_language": normalize_alert_locale(user.alert_language),
            "telegram_alerts_enabled": bool(user.telegram_alerts_enabled),
            "telegram_bot_key": (decrypt_payload(user.telegram_bot_token_encrypted).get("value") or "").strip() or None,
            "telegram_chat_id": (decrypt_payload(user.telegram_chat_id_encrypted).get("value") or "").strip() or None,
        },
        "grants": [{
            "platform": grant.platform,
            "is_enabled": grant.is_enabled,
            "max_symbols": grant.max_symbols,
            "max_daily_movements": grant.max_daily_movements,
            "notes": grant.notes,
        } for grant in grants],
        "connectors": [{
            "id": c.id,
            "platform": c.platform,
            "label": c.label,
            "mode": c.mode,
            "market_type": c.market_type,
            "is_enabled": c.is_enabled,
            "symbols": c.symbols_json.get("symbols", []),
            "allocation_mode": (c.config_json or {}).get("allocation_mode", "fixed"),
            "allocation_value": (c.config_json or {}).get("allocation_value", (c.config_json or {}).get("default_quantity", 0)),
            "has_saved_credentials": bool((decrypt_payload(c.encrypted_secret_blob) or {}).keys()),
            "config": c.config_json or {},
        } for c in connectors],
        "policies": [{
            "platform": p.platform,
            "display_name": p.display_name,
            "is_enabled_global": p.is_enabled_global,
            "user_enabled": grants_by_platform.get(p.platform).is_enabled if p.platform in grants_by_platform else False,
        } for p in db.query(PlatformPolicy).order_by(PlatformPolicy.display_name.asc()).all()],
        "strategy_control": {
            "managed_by_admin": strategy_control.managed_by_admin,
            "allowed_strategies": (strategy_control.allowed_strategies_json or {}).get("items", ALL_STRATEGIES),
            "all_strategies": ALL_STRATEGIES,
        },
        "telegram": {
            "alerts_enabled": bool(user.telegram_alerts_enabled),
            "bot_key": (decrypt_payload(user.telegram_bot_token_encrypted).get("value") or "").strip() or None,
            "chat_id": (decrypt_payload(user.telegram_chat_id_encrypted).get("value") or "").strip() or None,
        },
        "recent_runs": [{
            "id": run.id,
            "created_at": _safe_iso(run.created_at),
            "connector_id": run.connector_id,
            "connector_label": next((c.label for c in connectors if c.id == run.connector_id), "-"),
            "symbol": run.symbol,
            "display_symbol": _display_symbol(run.symbol),
            "status": run.status,
            "reason": _translate_status_reason(_trade_run_primary_reason(run)),
        } for run in recent_runs],
        "recent_sessions": [{
            "id": session.id,
            "strategy_slug": session.strategy_slug,
            "connector_label": next((c.label for c in connectors if c.id == session.connector_id), "-"),
            "market_type": normalize_market_type(session.market_type),
            "is_active": bool(session.is_active),
            "last_status": session.last_status,
            "last_error": session.last_error,
            "updated_at": _safe_iso(session.updated_at),
        } for session in recent_sessions],
    }


@router.get("/admin/overview")
def admin_overview(db=Depends(get_db), _: User = Depends(admin_user)):
    users = db.query(User).all()
    connectors = db.query(Connector).all()
    sessions = db.query(BotSession).all()
    recent_runs = db.query(TradeRun).order_by(TradeRun.created_at.desc()).limit(20).all()

    platform_summary: dict[str, dict[str, int]] = {}
    for connector in connectors:
        platform = str(connector.platform or "-")
        bucket = platform_summary.setdefault(platform, {"total": 0, "enabled": 0, "live": 0})
        bucket["total"] += 1
        if connector.is_enabled:
            bucket["enabled"] += 1
        if str(connector.mode or "").lower() == "live" and connector.is_enabled:
            bucket["live"] += 1

    events = []
    for run in recent_runs:
        primary_reason = _trade_run_primary_reason(run)
        events.append({
            "id": run.id,
            "created_at": _safe_iso(run.created_at),
            "symbol": _display_symbol(run.symbol),
            "status": run.status,
            "reason": _translate_status_reason(primary_reason),
            "connector_id": run.connector_id,
        })

    errored_sessions = [
        session for session in sessions
        if str(getattr(session, "last_status", "") or "").lower() in {"error", "failed"}
        or str(getattr(session, "last_error", "") or "").strip()
    ]

    return {
        "metrics": {
            "users_total": len(users),
            "users_active": sum(1 for item in users if item.is_active),
            "connectors_total": len(connectors),
            "connectors_enabled": sum(1 for item in connectors if item.is_enabled),
            "connectors_live": sum(1 for item in connectors if item.is_enabled and str(item.mode or "").lower() == "live"),
            "sessions_total": len(sessions),
            "sessions_active": sum(1 for item in sessions if item.is_active),
            "sessions_with_errors": len(errored_sessions),
            "recent_run_errors": sum(1 for item in recent_runs if str(item.status or "").lower().startswith(("error", "failed", "skipped"))),
        },
        "platforms": [
            {"platform": platform, **values}
            for platform, values in sorted(platform_summary.items(), key=lambda entry: entry[0])
        ],
        "events": events,
    }


@router.get("/admin/users/{user_id}/heartbeat")
def admin_user_heartbeat(user_id: int, db=Depends(get_db), _: User = Depends(admin_user)):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    connectors = db.query(Connector).filter(Connector.user_id == user_id, Connector.is_enabled.is_(True)).all()
    checks = []
    checked_at = datetime.utcnow().isoformat()
    for connector in connectors:
        try:
            client = get_client(connector)
            raw = client.test_connection()
            checks.append({
                "id": connector.id,
                "label": connector.label,
                "platform": connector.platform,
                "market_type": ensure_connector_market_type_state(connector, persist=True, db=db),
                "ok": True,
                "message": "Conector validado",
                "raw": raw,
            })
        except Exception as exc:
            checks.append({
                "id": connector.id,
                "label": connector.label,
                "platform": connector.platform,
                "market_type": ensure_connector_market_type_state(connector, persist=True, db=db),
                "ok": False,
                "message": str(exc),
                "raw": None,
            })
    return {"ok": all(item["ok"] for item in checks) if checks else True, "total": len(checks), "checked_at": checked_at, "checks": checks}


@router.post("/admin/users/{user_id}/kill-switch")
def admin_user_kill_switch(user_id: int, db=Depends(get_db), _: User = Depends(admin_user)):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    connector_ids = [item.id for item in db.query(Connector).filter(Connector.user_id == user_id, Connector.is_enabled.is_(True)).all()]
    return trigger_kill_switch(db, connector_ids=connector_ids or None, reason="admin_manual")


@router.post("/admin/users")
def admin_create_user(payload: AdminUserCreate, db=Depends(get_db), actor: User = Depends(admin_user)):
    clean_email = payload.email.strip().lower()
    clean_name = payload.name.strip()

    exists = db.query(User).filter(User.email == clean_email).first()
    if exists:
        detail = f"admin_create_user duplicate email={clean_email} actor_id={actor.id}"
        _alert_admin_failure("Admin User Creation", detail)
        raise HTTPException(status_code=400, detail="Cannot create user: email already exists")

    try:
        user = User(
            email=clean_email,
            name=clean_name,
            hashed_password=hash_password(payload.password),
            is_active=True,
            is_admin=False,
        )
        db.add(user)
        db.flush()
        ensure_user_grants(db, user)
        db.commit()
        db.refresh(user)
        return {"ok": True, "user_id": user.id}
    except HTTPException as exc:
        db.rollback()
        _alert_admin_failure("Admin User Creation", f"actor_id={actor.id} email={clean_email} detail={_extract_http_error_detail(exc)}")
        raise
    except Exception as exc:
        db.rollback()
        _alert_admin_failure("Admin User Creation", f"actor_id={actor.id} email={clean_email} error={exc}")
        raise HTTPException(status_code=500, detail="Unable to create user at this time")


@router.get("/admin/policies")
def admin_list_policies(db=Depends(get_db), _: User = Depends(admin_user)):
    policies = db.query(PlatformPolicy).order_by(PlatformPolicy.platform.asc()).all()
    return [{
        "platform": p.platform,
        "display_name": p.display_name,
        "is_enabled_global": p.is_enabled_global,
        "allow_manual_symbols": p.allow_manual_symbols,
        "top_symbols": (p.top_symbols_json or {}).get("symbols", []),
        "allowed_symbols": [],
        "guide": p.guide_json,
    } for p in policies]


@router.put("/admin/policies/{platform}")
def admin_update_policy(platform: str, payload: AdminPolicyUpdate, db=Depends(get_db), _: User = Depends(admin_user)):
    policy = db.query(PlatformPolicy).filter(PlatformPolicy.platform == platform).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    if payload.is_enabled_global is not None:
        policy.is_enabled_global = payload.is_enabled_global
    if payload.allow_manual_symbols is not None:
        policy.allow_manual_symbols = payload.allow_manual_symbols
    if payload.top_symbols is not None:
        policy.top_symbols_json = {"symbols": payload.top_symbols}
    policy.allowed_symbols_json = {"symbols": []}
    db.commit()
    return {"ok": True}


@router.get("/admin/pricing-config")
def admin_get_pricing_config(db=Depends(get_db), _: User = Depends(admin_user)):
    pricing = db.query(PricingConfig).first()
    if not pricing:
        raise HTTPException(status_code=404, detail="Pricing config missing")
    return {
        "id": pricing.id,
        "base_commission_usd": pricing.base_commission_usd,
        "cost_per_app_usd": pricing.cost_per_app_usd,
        "cost_per_symbol_usd": pricing.cost_per_symbol_usd,
        "cost_per_movement_usd": pricing.cost_per_movement_usd,
        "cost_per_gb_ram_usd": pricing.cost_per_gb_ram_usd,
        "cost_per_gb_disk_usd": pricing.cost_per_gb_disk_usd,
        "suggested_ram_per_app_gb": pricing.suggested_ram_per_app_gb,
        "suggested_disk_per_app_gb": pricing.suggested_disk_per_app_gb,
    }


@router.put("/admin/pricing-config")
def admin_update_pricing_config(payload: AdminPricingConfigUpdate, db=Depends(get_db), _: User = Depends(admin_user)):
    pricing = db.query(PricingConfig).first()
    if not pricing:
        raise HTTPException(status_code=404, detail="Pricing config missing")
    pricing.base_commission_usd = payload.base_commission_usd
    pricing.cost_per_app_usd = payload.cost_per_app_usd
    pricing.cost_per_symbol_usd = payload.cost_per_symbol_usd
    pricing.cost_per_movement_usd = payload.cost_per_movement_usd
    pricing.cost_per_gb_ram_usd = payload.cost_per_gb_ram_usd
    pricing.cost_per_gb_disk_usd = payload.cost_per_gb_disk_usd
    pricing.suggested_ram_per_app_gb = payload.suggested_ram_per_app_gb
    pricing.suggested_disk_per_app_gb = payload.suggested_disk_per_app_gb
    db.commit()
    return {"ok": True}


@router.get("/admin/plans")
def admin_list_plans(db=Depends(get_db), _: User = Depends(admin_user)):
    plans = db.query(PlanConfig).order_by(PlanConfig.sort_order.asc(), PlanConfig.id.asc()).all()
    return [{
        "id": plan.id,
        "name": plan.name,
        "description": plan.description,
        "apps": plan.apps,
        "symbols": plan.symbols,
        "daily_movements": plan.daily_movements,
        "monthly_price_usd": plan.monthly_price_usd,
        "is_custom": plan.is_custom,
        "is_active": plan.is_active,
        "sort_order": plan.sort_order,
    } for plan in plans]


@router.post("/admin/plans")
def admin_create_plan(payload: AdminPlanConfigPayload, db=Depends(get_db), _: User = Depends(admin_user)):
    plan = PlanConfig(**payload.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return {"ok": True, "id": plan.id}


@router.put("/admin/plans/{plan_id}")
def admin_update_plan(plan_id: int, payload: AdminPlanConfigPayload, db=Depends(get_db), _: User = Depends(admin_user)):
    plan = db.query(PlanConfig).filter(PlanConfig.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    for key, value in payload.model_dump().items():
        setattr(plan, key, value)
    db.commit()
    return {"ok": True}


@router.delete("/admin/plans/{plan_id}")
def admin_delete_plan(plan_id: int, db=Depends(get_db), _: User = Depends(admin_user)):
    plan = db.query(PlanConfig).filter(PlanConfig.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    db.delete(plan)
    db.commit()
    return {"ok": True}


@router.get("/admin/grants")
def admin_list_grants(db=Depends(get_db), _: User = Depends(admin_user)):
    grants = db.query(UserPlatformGrant).order_by(UserPlatformGrant.user_id.asc(), UserPlatformGrant.platform.asc()).all()
    return [{
        "id": g.id,
        "user_id": g.user_id,
        "platform": g.platform,
        "is_enabled": g.is_enabled,
        "max_symbols": g.max_symbols,
        "max_daily_movements": g.max_daily_movements,
        "notes": g.notes,
    } for g in grants]


@router.put("/admin/grants")
def admin_upsert_grant(payload: AdminGrantUpdate, db=Depends(get_db), _: User = Depends(admin_user)):
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    grant = get_user_grant(db, payload.user_id, payload.platform)
    if not grant:
        grant = UserPlatformGrant(user_id=payload.user_id, platform=payload.platform)
        db.add(grant)
    grant.is_enabled = payload.is_enabled
    grant.max_symbols = payload.max_symbols
    grant.max_daily_movements = payload.max_daily_movements
    grant.notes = payload.notes
    db.commit()
    return {"ok": True}


@router.put("/admin/users/{user_id}/strategy-control")
def admin_update_strategy_control(user_id: int, payload: AdminStrategyControlUpdate, db=Depends(get_db), _: User = Depends(admin_user)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    control = _ensure_strategy_control(db, user_id)
    control.managed_by_admin = payload.managed_by_admin
    allowed = [s for s in payload.allowed_strategies if s in ALL_STRATEGIES]
    control.allowed_strategies_json = {"items": allowed or ALL_STRATEGIES}
    db.commit()
    return {"ok": True}
