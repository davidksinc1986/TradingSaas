import json

from fastapi import APIRouter, Depends, HTTPException

from app.db import get_db
from app.core import settings
from app.models import Connector, PlanConfig, PlatformPolicy, PricingConfig, TradeLog, TradeRun, User, UserPlatformGrant, UserStrategyControl
from app.routers.deps import admin_user, current_user
from app.schemas import (
    AdminUserCreate,
    AdminGrantUpdate,
    AdminPlanConfigPayload,
    AdminPolicyUpdate,
    AdminPricingConfigUpdate,
    AdminStrategyControlUpdate,
    AdminUserUpdate,
    ConnectorCreate,
    ConnectorUpdate,
    StrategyRequest,
    TradingViewWebhook,
)
from app.security import encrypt_payload, hash_password
from app.services.connectors import get_client
from app.services.policies import ensure_user_grants, get_user_grant, validate_connector_request
from app.services.pricing import estimate_monthly_cost
from app.services.trading import dashboard_data, run_strategy

router = APIRouter(prefix="/api", tags=["api"])
ROOT_ADMIN_EMAIL = (settings.admin_email or "davidksinc").strip().lower()
ALL_STRATEGIES = ["ema_rsi", "mean_reversion_zscore", "momentum_breakout", "macd_trend_pullback", "bollinger_rsi_reversal", "adx_trend_follow", "stochastic_rebound"]


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
    return {"id": user.id, "email": user.email, "name": user.name, "phone": user.phone, "is_admin": user.is_admin}


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

    db.commit()
    return {"ok": True, "id": user.id, "name": user.name, "phone": user.phone}


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
    return [{
        "id": c.id,
        "platform": c.platform,
        "label": c.label,
        "mode": c.mode,
        "market_type": getattr(c, "market_type", "spot"),
        "is_enabled": c.is_enabled,
        "symbols": c.symbols_json.get("symbols", []),
        "config": c.config_json,
        "created_at": c.created_at.isoformat(),
    } for c in connectors]


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
    return {"ok": True}


@router.delete("/connectors/{connector_id}")
def delete_connector(connector_id: int, db=Depends(get_db), user: User = Depends(current_user)):
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    if connector.user_id != user.id:
        admin_user(user)
    db.delete(connector)
    db.commit()
    return {"ok": True}


@router.post("/connectors/{connector_id}/test")
def test_connector(connector_id: int, db=Depends(get_db), user=Depends(current_user)):
    connector = db.query(Connector).filter(Connector.id == connector_id, Connector.user_id == user.id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    client = get_client(connector)
    try:
        data = client.test_connection()
        return {"status": "ok", "message": "Connection test completed", "raw": data}
    except Exception as exc:
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


@router.get("/dashboard")
def dashboard(db=Depends(get_db), user=Depends(current_user)):
    data = dashboard_data(db, user.id)
    return {
        **data,
        "latest_trades": [{
            "id": t.id,
            "platform": t.platform,
            "symbol": t.symbol,
            "side": t.side,
            "quantity": t.quantity,
            "price": t.price,
            "status": t.status,
            "pnl": t.pnl,
            "created_at": t.created_at.isoformat(),
        } for t in data["latest_trades"]],
    }


@router.get("/market/top-strength")
async def market_top_strength(limit: int = 10, user=Depends(current_user)):
    _ = user
    import httpx

    target = min(max(limit, 1), 20)
    url = "https://api.binance.com/api/v3/ticker/24hr"
    async with httpx.AsyncClient(timeout=8.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        payload = response.json()

    usdt_pairs = [item for item in payload if str(item.get("symbol", "")).endswith("USDT")]
    ranked = sorted(usdt_pairs, key=lambda item: float(item.get("priceChangePercent", 0) or 0), reverse=True)[:target]
    return [{
        "symbol": item.get("symbol"),
        "price": float(item.get("lastPrice", 0) or 0),
        "change_percent": float(item.get("priceChangePercent", 0) or 0),
        "volume": float(item.get("quoteVolume", 0) or 0),
    } for item in ranked]


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
    return {"ok": True, "message": "Webhook processed", "status": status}


@router.get("/heartbeat")
def connector_heartbeat(db=Depends(get_db), user=Depends(current_user)):
    connectors = db.query(Connector).filter(Connector.user_id == user.id, Connector.is_enabled.is_(True)).all()
    checks = []
    for connector in connectors:
        client = get_client(connector)
        try:
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

    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.is_admin is not None:
        user.is_admin = payload.is_admin

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
def admin_create_user(payload: AdminUserCreate, db=Depends(get_db), _: User = Depends(admin_user)):
    exists = db.query(User).filter(User.email == payload.email).first()
    if exists:
        raise HTTPException(status_code=400, detail="User already exists")
    user = User(
        email=payload.email,
        name=payload.name,
        hashed_password=hash_password(payload.password),
        is_active=True,
        is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    ensure_user_grants(db, user)
    return {"ok": True, "user_id": user.id}


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
