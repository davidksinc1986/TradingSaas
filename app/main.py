from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core import settings
from sqlalchemy import inspect, text

from app.db import Base, SessionLocal, engine
from app.models import StrategyProfile, User, UserStrategyControl
from app.routers import api, auth, views
from app.security import hash_password
from app.services.policies import ensure_user_grants, seed_platform_policies
from app.services.pricing import ensure_pricing_seed

app = FastAPI(title=settings.app_name)

Base.metadata.create_all(bind=engine)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(views.router)
app.include_router(auth.router)
app.include_router(api.router)




def ensure_schema_updates(db):
    inspector = inspect(engine)
    if not inspector.has_table("users"):
        return

    existing_columns = {column["name"] for column in inspector.get_columns("users")}
    if "phone" not in existing_columns:
        db.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR(40)"))
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
        for user in db.query(User).all():
            ensure_user_grants(db, user)
            control = db.query(UserStrategyControl).filter(UserStrategyControl.user_id == user.id).first()
            if not control:
                db.add(UserStrategyControl(user_id=user.id, managed_by_admin=False, allowed_strategies_json={"items": ["ema_rsi", "mean_reversion_zscore", "momentum_breakout"]}))
        db.commit()
    finally:
        db.close()


@app.get("/health")
def health():
    return {"ok": True, "app": settings.app_name}
