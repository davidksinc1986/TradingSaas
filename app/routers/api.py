import csv
import io
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.db import get_db
from app.core import settings
from app.models import BotSession, Connector, PlanConfig, PlatformPolicy, PricingConfig, StrategyTemplate, TradeLog, TradeRun, User, UserPlatformGrant, UserStrategyControl
from app.routers.deps import admin_user, current_user
from app.schemas import (
    AdminUserCreate,
    AdminGrantUpdate,
    AdminPlanConfigPayload,
    AdminPolicyUpdate,
    AdminPricingConfigUpdate,
    AdminStrategyControlUpdate,
    StrategyControlUpdate,
    BotSessionCopyPayload,
    BotSessionCreate,
    BotSessionUpdate,
    AdminUserUpdate,
    ConnectorCreate,
    ConnectorUpdate,
    StrategyRequest,
    StrategyTemplateApplyPayload,
    StrategyTemplateCreate,
    TradingViewWebhook,
)
from app.security import encrypt_payload, hash_password
from app.services.alerts import (
    format_failure_message,
    format_user_failure_message,
    format_user_info_message,
    normalize_alert_locale,
    send_telegram_alert_sync,
    send_user_telegram_alert,
    send_user_telegram_test_alert,
    user_has_telegram_config,
)
from app.services.connectors import get_client
from app.services.market import price_check
from app.services.policies import ensure_user_grants, get_user_grant, validate_connector_request
from app.services.pricing import estimate_monthly_cost
from app.services.position_lifecycle import trigger_kill_switch
from app.services.trading import activity_metrics, dashboard_data, run_strategy, sync_positions_with_exchange
from app.services.strategies import ALL_STRATEGIES

router = APIRouter(prefix="/api", tags=["api"])
logger = logging.getLogger(__name__)
ROOT_ADMIN_EMAIL = (settings.admin_email or "davidksinc").strip().lower()
TIMEFRAME_TO_MINUTES = {
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




def _alert_admin_failure(scope: str, detail: str) -> None:
    try:
        send_telegram_alert_sync(format_failure_message(scope, detail))
    except Exception:
        pass


def _extract_http_error_detail(exc: HTTPException) -> str:
    if isinstance(exc.detail, str):
        return exc.detail
    return json.dumps(exc.detail, ensure_ascii=False)


def _normalize_timeframe(value: str) -> str:
    clean = str(value or "").strip().lower()
    if not clean:
        return "5m"
    return clean


def _notify_user_info(user: User, *, title: str, detail: str,
                      connector_label: str | None = None, platform: str | None = None,
                      symbol: str | None = None) -> None:
    try:
        send_user_telegram_alert(
            user,
            format_user_info_message(
                locale=user.alert_language,
                title=title,
                detail=detail,
                connector_label=connector_label,
                platform=platform,
                symbol=symbol,
            ),
        )
    except Exception:
        logger.exception("Failed sending informational Telegram alert for user_id=%s", getattr(user, "id", "?"))


def _interval_from_timeframe(timeframe: str, fallback: int = 5) -> int:
    clean = _normalize_timeframe(timeframe)
    return TIMEFRAME_TO_MINUTES.get(clean, max(int(fallback or 5), 1))


def _safe_float(value, fallback: float = 0.0) -> float:
    try:
        parsed = float(value)
        if parsed != parsed:  # NaN guard
            return fallback
        return parsed
    except (TypeError, ValueError):
        return fallback


def _safe_iso(dt_value) -> str | None:
    return dt_value.isoformat() if dt_value else None


def _safe_json_object(value) -> dict:
    if isinstance(value, dict):
        return value
    return {}


def _safe_symbols(value) -> list[str]:
    if isinstance(value, dict):
        raw = value.get("symbols", [])
    elif isinstance(value, list):
        raw = value
    else:
        raw = []
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if str(item).strip()]


def _estimate_trade_investment(trade: TradeLog, user: User) -> float:
    meta = trade.meta_json or {}
    capital_allocated = _safe_float(meta.get("capital_allocated"))
    if capital_allocated > 0:
        return capital_allocated
    if str(getattr(user, "trade_amount_mode", "fixed_usd") or "fixed_usd").lower() == "fixed_usd":
        fixed_amount = _safe_float(getattr(user, "fixed_trade_amount_usd", 10.0), 10.0)
        if fixed_amount > 0:
            return fixed_amount
    return _safe_float(trade.quantity) * _safe_float(trade.price)


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
        "telegram_alerts_enabled": user.telegram_alerts_enabled,
        "telegram_chat_id": ("****" if user.telegram_chat_id_encrypted else ""),
        "alert_language": normalize_alert_locale(user.alert_language),
        "has_telegram_bot_key": bool(user.telegram_bot_token_encrypted),
        "telegram_ready": user_has_telegram_config(user),
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

    next_alert_enabled = payload.get("telegram_alerts_enabled")
    if next_alert_enabled is not None:
        user.telegram_alerts_enabled = bool(next_alert_enabled)

    next_language = payload.get("alert_language")
    if next_language is not None:
        user.alert_language = normalize_alert_locale(str(next_language))

    next_telegram_bot_key = payload.get("telegram_bot_key")
    if next_telegram_bot_key is not None:
        clean_bot_key = str(next_telegram_bot_key).strip()
        user.telegram_bot_token_encrypted = encrypt_payload({"value": clean_bot_key}) if clean_bot_key else None

    next_telegram_chat_id = payload.get("telegram_chat_id")
    if next_telegram_chat_id is not None:
        clean_chat_id = str(next_telegram_chat_id).strip()
        user.telegram_chat_id_encrypted = encrypt_payload({"value": clean_chat_id}) if clean_chat_id else None

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
    telegram_ready = user_has_telegram_config(user)
    return {
        "ok": True,
        "id": user.id,
        "name": user.name,
        "phone": user.phone,
        "telegram_alerts_enabled": user.telegram_alerts_enabled,
        "alert_language": normalize_alert_locale(user.alert_language),
        "has_telegram_bot_key": bool(user.telegram_bot_token_encrypted),
        "has_telegram_chat_id": bool(user.telegram_chat_id_encrypted),
        "telegram_ready": telegram_ready,
        "trade_amount_mode": user.trade_amount_mode,
        "fixed_trade_amount_usd": float(user.fixed_trade_amount_usd or 10),
        "trade_balance_percent": float(user.trade_balance_percent or 10),
    }


@router.post("/me/telegram/test")
def me_telegram_test(db=Depends(get_db), user=Depends(current_user)):
    _ = db
    if not user.telegram_alerts_enabled:
        raise HTTPException(status_code=400, detail="Activa las alertas de Telegram antes de probar el envío")
    if not user_has_telegram_config(user):
        raise HTTPException(status_code=400, detail="Faltan bot key o chat id de Telegram")
    ok = send_user_telegram_test_alert(user)
    if not ok:
        raise HTTPException(status_code=502, detail="No se pudo enviar el mensaje de prueba a Telegram")
    return {"ok": True, "message": "Mensaje de prueba enviado a Telegram"}


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
            payload.append({
                "id": connector.id,
                "platform": connector.platform,
                "label": connector.label,
                "mode": connector.mode,
                "market_type": getattr(connector, "market_type", "spot") or "spot",
                "is_enabled": bool(connector.is_enabled),
                "symbols": _safe_symbols(getattr(connector, "symbols_json", {})),
                "config": _safe_json_object(getattr(connector, "config_json", {})),
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
                "market_type": getattr(connector, "market_type", "spot") or "spot",
                "is_enabled": bool(getattr(connector, "is_enabled", False)),
                "symbols": [],
                "config": {},
                "created_at": _safe_iso(getattr(connector, "created_at", None)),
            })

    if serialization_errors:
        _alert_admin_failure("API /api/connectors serialization", " | ".join(serialization_errors)[:1500])
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
    validate_connector_request(db, target_user, payload.platform, payload.symbols)
    connector = Connector(
        user_id=target_user.id,
        platform=payload.platform,
        label=payload.label,
        mode=payload.mode,
        market_type=payload.market_type,
        symbols_json={"symbols": payload.symbols},
        config_json=payload.config,
        encrypted_secret_blob=encrypt_payload(payload.secrets),
    )
    db.add(connector)
    db.commit()
    db.refresh(connector)
    _notify_user_info(
        target_user,
        title="Conector creado",
        detail=f"Se creó el conector {connector.label} en modo {connector.mode} para {len(payload.symbols)} símbolos.",
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
    if payload.market_type is not None:
        connector.market_type = payload.market_type
    if payload.symbols is not None:
        connector.symbols_json = {"symbols": payload.symbols}
    if payload.config is not None:
        current = connector.config_json or {}
        current.update(payload.config)
        connector.config_json = current
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
    client = get_client(connector)
    try:
        data = client.test_connection()
        _notify_user_info(
            user,
            title="Prueba de conector exitosa",
            detail=f"{connector.label} respondió correctamente a la prueba de conexión.",
            connector_label=connector.label,
            platform=connector.platform,
        )
        return {"status": "ok", "message": "Connection test completed", "raw": data}
    except Exception as exc:
        send_user_telegram_alert(user, format_user_failure_message(
            locale=user.alert_language,
            scope="connector_test",
            detail=str(exc),
            connector_label=connector.label,
            platform=connector.platform,
        ))
        return {"status": "error", "message": str(exc), "raw": {"platform": connector.platform}}


@router.put("/connectors/{connector_id}/credentials")
def update_connector_credentials(connector_id: int, payload: ConnectorUpdate, db=Depends(get_db), user=Depends(current_user)):
    connector = db.query(Connector).filter(Connector.id == connector_id, Connector.user_id == user.id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    if payload.secrets is not None:
        connector.encrypted_secret_blob = encrypt_payload(payload.secrets)

    if payload.config is not None:
        current = connector.config_json or {}
        current.update(payload.config)
        connector.config_json = current

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
        run_source="manual",
    )
    status_counts: dict[str, int] = {}
    for item in result:
        status = str(item.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    _notify_user_info(
        user,
        title="Estrategia ejecutada manualmente",
        detail=f"{payload.strategy_slug} sobre {len(payload.symbols)} símbolos. Resultado: "
               + ", ".join(f"{status}={count}" for status, count in sorted(status_counts.items())),
        symbol=", ".join(payload.symbols[:3]) if payload.symbols else None,
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
            capital = _safe_float(getattr(session.user, "fixed_trade_amount_usd", 0) or config.get("allocation_value", config.get("default_quantity", 0)) or 0)
            payload.append({
                "id": session.id,
                "connector_id": session.connector_id,
                "connector_label": connector.label if connector else "-",
                "platform": connector.platform if connector else "-",
                "mode": connector.mode if connector else "-",
                "strategy_slug": session.strategy_slug,
                "timeframe": session.timeframe,
                "symbols": symbols,
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
                "capital_currency": "USDT",
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
                "strategy_slug": getattr(session, "strategy_slug", "-"),
                "timeframe": getattr(session, "timeframe", "5m"),
                "symbols": [],
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

    risk_value = payload.risk_per_trade / 100 if payload.risk_per_trade > 1 else payload.risk_per_trade
    ml_value = payload.min_ml_probability / 100 if payload.min_ml_probability > 1 else payload.min_ml_probability

    normalized_timeframe = _normalize_timeframe(payload.timeframe)
    session = BotSession(
        user_id=user.id,
        connector_id=connector.id,
        strategy_slug=payload.strategy_slug,
        timeframe=normalized_timeframe,
        symbols_json={"symbols": payload.symbols},
        interval_minutes=_interval_from_timeframe(normalized_timeframe, payload.interval_minutes),
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
        is_active=True,
        last_status="queued",
        next_run_at=datetime.utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    _notify_user_info(
        user,
        title="Bot 24/7 activado",
        detail=f"Sesión #{session.id} creada con estrategia {session.strategy_slug} en timeframe {session.timeframe}. La primera corrida quedó en cola para ejecutarse automáticamente.",
        connector_label=connector.label,
        platform=connector.platform,
    )

    return {"ok": True, "session_id": session.id}


@router.put("/bot-sessions/{session_id}")
def update_bot_session(session_id: int, payload: BotSessionUpdate, db=Depends(get_db), user=Depends(current_user)):
    session = db.query(BotSession).filter(BotSession.id == session_id, BotSession.user_id == user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Bot session not found")

    control = _ensure_strategy_control(db, user.id)
    allowed = (control.allowed_strategies_json or {}).get("items", ALL_STRATEGIES)

    if payload.is_active is not None:
        session.is_active = payload.is_active
    if payload.symbols is not None:
        session.symbols_json = {"symbols": payload.symbols}
    if payload.strategy_slug is not None:
        if control.managed_by_admin and payload.strategy_slug not in allowed:
            raise HTTPException(status_code=403, detail="Strategy is managed by admin for this user")
        session.strategy_slug = payload.strategy_slug
    if payload.timeframe is not None:
        normalized_timeframe = _normalize_timeframe(payload.timeframe)
        session.timeframe = normalized_timeframe
        session.interval_minutes = _interval_from_timeframe(normalized_timeframe, payload.interval_minutes or session.interval_minutes)
    elif payload.interval_minutes is not None:
        session.interval_minutes = payload.interval_minutes

    if payload.risk_per_trade is not None:
        session.risk_per_trade = payload.risk_per_trade / 100 if payload.risk_per_trade > 1 else payload.risk_per_trade
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

    db.commit()
    connector = db.query(Connector).filter(Connector.id == session.connector_id).first()
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
    session = db.query(BotSession).filter(BotSession.id == session_id, BotSession.user_id == user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Bot session not found")
    connector = db.query(Connector).filter(Connector.id == session.connector_id).first()
    detail = f"Se eliminó la sesión #{session.id} con estrategia {session.strategy_slug}."
    db.delete(session)
    db.commit()
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
    source = db.query(BotSession).filter(BotSession.id == session_id, BotSession.user_id == user.id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Bot session not found")

    target_connector_id = payload.connector_id or source.connector_id
    connector = db.query(Connector).filter(Connector.id == target_connector_id, Connector.user_id == user.id, Connector.is_enabled.is_(True)).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Enabled connector not found")

    cloned = BotSession(
        user_id=user.id,
        connector_id=connector.id,
        strategy_slug=source.strategy_slug,
        timeframe=source.timeframe,
        symbols_json={"symbols": payload.symbols if payload.symbols is not None else ((source.symbols_json or {}).get("symbols", []))},
        interval_minutes=source.interval_minutes,
        risk_per_trade=source.risk_per_trade,
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
    )
    db.add(cloned)
    db.commit()
    db.refresh(cloned)
    _notify_user_info(
        user,
        title="Bot clonado",
        detail=f"Se clonó la sesión #{source.id} hacia la nueva sesión #{cloned.id}.",
        connector_label=connector.label,
        platform=connector.platform,
    )
    return {"ok": True, "session_id": cloned.id}


@router.get("/execution-logs/download")
def download_execution_logs(limit: int = 500, db=Depends(get_db), user=Depends(current_user)):
    target = min(max(limit, 1), 2000)
    runs = db.query(TradeRun).filter(TradeRun.user_id == user.id).order_by(TradeRun.created_at.desc()).limit(target).all()

    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["id", "created_at", "connector_id", "symbol", "timeframe", "signal", "status", "ml_probability", "quantity", "notes_json"])
    for run in runs:
        writer.writerow([
            run.id,
            run.created_at.isoformat() if run.created_at else "",
            run.connector_id,
            run.symbol,
            run.timeframe,
            run.signal,
            run.status,
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
            "timeframe": source.timeframe,
            "risk_per_trade": source.risk_per_trade,
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
    session = BotSession(
        user_id=user.id,
        connector_id=connector.id,
        strategy_slug=cfg.get("strategy_slug", "ema_rsi"),
        timeframe=cfg.get("timeframe", "5m"),
        symbols_json={"symbols": payload.symbols},
        interval_minutes=int(cfg.get("interval_minutes", _interval_from_timeframe(cfg.get("timeframe", "5m"), 5))),
        risk_per_trade=float(cfg.get("risk_per_trade", 0.03)),
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
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"ok": True, "session_id": session.id}


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
        payload.append({
            "id": run.id,
            "connector_id": run.connector_id,
            "symbol": run.symbol,
            "strategy_slug": run.strategy_slug,
            "timeframe": run.timeframe,
            "signal": run.signal,
            "status": run.status,
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
    for connector in connectors:
        try:
            client = get_client(connector)
            raw = client.test_connection()
            checks.append({
                "id": connector.id,
                "label": connector.label,
                "platform": connector.platform,
                "ok": True,
                "message": "Conector validado",
                "raw": raw,
            })
        except Exception as exc:
            checks.append({
                "id": connector.id,
                "label": connector.label,
                "platform": connector.platform,
                "ok": False,
                "message": str(exc),
                "raw": None,
            })
            send_user_telegram_alert(user, format_user_failure_message(
                locale=user.alert_language,
                scope="heartbeat",
                detail=str(exc),
                connector_label=connector.label,
                platform=connector.platform,
            ))
    return {
        "ok": all(item["ok"] for item in checks) if checks else True,
        "total": len(checks),
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
        next_email = str(payload.email).strip().lower()
        existing = db.query(User).filter(User.email == next_email, User.id != user.id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already exists")
        user.email = next_email

    if payload.name is not None:
        user.name = str(payload.name).strip()

    if payload.phone is not None:
        clean_phone = str(payload.phone).strip()
        if clean_phone and (len(clean_phone) < 7 or len(clean_phone) > 40):
            raise HTTPException(status_code=400, detail="Phone must be between 7 and 40 characters")
        user.phone = clean_phone or None

    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.is_admin is not None:
        user.is_admin = payload.is_admin

    db.commit()
    return {"ok": True}




@router.delete("/admin/users/{user_id}")
def admin_delete_user(user_id: int, db=Depends(get_db), actor: User = Depends(admin_user)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Cannot find user")

    if _is_root_admin(user):
        raise HTTPException(status_code=403, detail=f"{ROOT_ADMIN_EMAIL} is hierarchical and cannot be deleted")

    if user.id == actor.id:
        raise HTTPException(status_code=403, detail="You cannot delete your own account")

    try:
        db.delete(user)
        db.commit()
        return {"ok": True}
    except Exception as exc:
        db.rollback()
        _alert_admin_failure("Admin User Delete", f"actor_id={actor.id} user_id={user_id} error={exc}")
        raise HTTPException(status_code=500, detail="Unable to delete user at this time")
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

    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "is_admin": user.is_admin,
            "is_active": user.is_active,
            "phone": user.phone,
            "is_root": _is_root_admin(user),
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
        }
    }


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
        "allowed_symbols": (p.allowed_symbols_json or {}).get("symbols", []),
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
    if payload.allowed_symbols is not None:
        policy.allowed_symbols_json = {"symbols": payload.allowed_symbols}
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
