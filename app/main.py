import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.core import settings
from sqlalchemy import inspect, text

from app.db import Base, SessionLocal, engine
from app.models import BotSession, StrategyProfile, User, UserStrategyControl
from app.routers import api, auth, views
from app.security import hash_password
from app.services.alerts import format_failure_message, send_telegram_alert
from app.services.policies import ensure_user_grants, seed_platform_policies
from app.services.pricing import ensure_pricing_seed
from app.services.bot_runner import start_bot_worker, stop_bot_worker

app = FastAPI(title=settings.app_name)
logger = logging.getLogger("trading_saas")

Base.metadata.create_all(bind=engine)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(views.router)
app.include_router(auth.router)
app.include_router(api.router)


class FailureAlertMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            if response.status_code >= 500:
                detail = f"{request.method} {request.url.path} -> status {response.status_code}"
                await send_telegram_alert(format_failure_message("HTTP 5xx", detail))
            return response
        except Exception as exc:
            trace = traceback.format_exc(limit=12)
            detail = f"{request.method} {request.url.path} | {exc}\n{trace}"
            await send_telegram_alert(format_failure_message("Unhandled Exception", detail))
            logger.exception("Unhandled exception for %s %s", request.method, request.url.path)
            raise


app.add_middleware(FailureAlertMiddleware)


def ensure_schema_updates(db):
    inspector = inspect(engine)

    def add_missing_columns(table_name: str, statements: dict[str, str]):
        if not inspector.has_table(table_name):
            return
        existing = {column["name"] for column in inspector.get_columns(table_name)}
        for column_name, statement in statements.items():
            if column_name not in existing:
                db.execute(text(statement))

    add_missing_columns("users", {
        "phone": "ALTER TABLE users ADD COLUMN phone VARCHAR(40)",
        "telegram_bot_token_encrypted": "ALTER TABLE users ADD COLUMN telegram_bot_token_encrypted TEXT",
        "telegram_chat_id_encrypted": "ALTER TABLE users ADD COLUMN telegram_chat_id_encrypted TEXT",
        "telegram_alerts_enabled": "ALTER TABLE users ADD COLUMN telegram_alerts_enabled BOOLEAN DEFAULT 0",
        "alert_language": "ALTER TABLE users ADD COLUMN alert_language VARCHAR(5) DEFAULT 'es'",
        "trade_amount_mode": "ALTER TABLE users ADD COLUMN trade_amount_mode VARCHAR(20) DEFAULT 'fixed_usd'",
        "fixed_trade_amount_usd": "ALTER TABLE users ADD COLUMN fixed_trade_amount_usd FLOAT DEFAULT 10",
        "trade_balance_percent": "ALTER TABLE users ADD COLUMN trade_balance_percent FLOAT DEFAULT 10",
    })

    add_missing_columns("connectors", {
        "market_type": "ALTER TABLE connectors ADD COLUMN market_type VARCHAR(20) DEFAULT 'spot'",
    })

    add_missing_columns("bot_sessions", {
        "stop_loss_mode": "ALTER TABLE bot_sessions ADD COLUMN stop_loss_mode VARCHAR(20) DEFAULT 'percent'",
        "stop_loss_value": "ALTER TABLE bot_sessions ADD COLUMN stop_loss_value FLOAT DEFAULT 1.0",
        "take_profit_mode": "ALTER TABLE bot_sessions ADD COLUMN take_profit_mode VARCHAR(20) DEFAULT 'percent'",
        "take_profit_value": "ALTER TABLE bot_sessions ADD COLUMN take_profit_value FLOAT DEFAULT 1.5",
        "trailing_stop_mode": "ALTER TABLE bot_sessions ADD COLUMN trailing_stop_mode VARCHAR(20) DEFAULT 'percent'",
        "trailing_stop_value": "ALTER TABLE bot_sessions ADD COLUMN trailing_stop_value FLOAT DEFAULT 0.8",
        "indicator_exit_enabled": "ALTER TABLE bot_sessions ADD COLUMN indicator_exit_enabled BOOLEAN DEFAULT 0",
        "indicator_exit_rule": "ALTER TABLE bot_sessions ADD COLUMN indicator_exit_rule VARCHAR(30) DEFAULT 'macd_cross'",
    })

    db.commit()


@app.on_event("startup")
def bootstrap():
    db = SessionLocal()
    try:
        try:
            ensure_schema_updates(db)
        except Exception:
            db.rollback()
        seeds = [
            ("ema_rsi", "EMA + RSI", "Cruce de EMAs con filtro RSI", {"ema_fast": 12, "ema_slow": 26, "rsi_buy_max": 68}),
            ("mean_reversion_zscore", "Mean Reversion Z-Score", "Reversión a la media por desviación estadística", {"z_buy": -1.8, "z_sell": 1.8}),
            ("momentum_breakout", "Momentum Breakout", "Rompimiento de rango de 20 velas", {"window": 20}),
        ]
        for slug, name, description, params in seeds:
            exists = db.query(StrategyProfile).filter(StrategyProfile.slug == slug).first()
            if not exists:
                db.add(StrategyProfile(slug=slug, name=name, description=description, params_json=params))

        admin = db.query(User).filter(User.email == settings.admin_email).first()
        if not admin:
            legacy_admin = db.query(User).filter(User.email == "davidksinc").first()
            if legacy_admin:
                legacy_admin.email = settings.admin_email
                legacy_admin.name = settings.admin_name
                legacy_admin.is_admin = True
                legacy_admin.is_active = True
                admin = legacy_admin

        if not admin:
            admin = User(
                email=settings.admin_email,
                name=settings.admin_name,
                hashed_password=hash_password(settings.admin_password),
                is_active=True,
                is_admin=True,
            )
            db.add(admin)
            db.flush()
        seed_platform_policies(db)
        ensure_pricing_seed(db)
        if not inspect(engine).has_table("bot_sessions"):
            BotSession.__table__.create(bind=engine, checkfirst=True)

        for user in db.query(User).all():
            ensure_user_grants(db, user)
            control = db.query(UserStrategyControl).filter(UserStrategyControl.user_id == user.id).first()
            if not control:
                db.add(UserStrategyControl(user_id=user.id, managed_by_admin=False, allowed_strategies_json={"items": ["ema_rsi", "mean_reversion_zscore", "momentum_breakout"]}))
        db.commit()
    except Exception as exc:
        detail = f"bootstrap startup failure: {exc}\n{traceback.format_exc(limit=12)}"
        try:
            import asyncio

            asyncio.run(send_telegram_alert(format_failure_message("Startup", detail)))
        except Exception:
            logger.exception("Could not send startup Telegram alert")
        raise
    finally:
        db.close()


@app.get("/health")
def health():
    return {"ok": True, "app": settings.app_name}


@app.on_event("startup")
def start_background_worker():
    start_bot_worker()


@app.on_event("shutdown")
def stop_background_worker():
    stop_bot_worker()
