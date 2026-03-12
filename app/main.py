from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core import settings
from app.db import Base, SessionLocal, engine
from app.models import StrategyProfile, User
from app.routers import api, auth, views
from app.security import hash_password
from app.services.policies import ensure_user_grants, seed_platform_policies

app = FastAPI(title=settings.app_name)

Base.metadata.create_all(bind=engine)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(views.router)
app.include_router(auth.router)
app.include_router(api.router)


@app.on_event("startup")
def bootstrap():
    db = SessionLocal()
    try:
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
        for user in db.query(User).all():
            ensure_user_grants(db, user)
        db.commit()
    finally:
        db.close()


@app.get("/health")
def health():
    return {"ok": True, "app": settings.app_name}
