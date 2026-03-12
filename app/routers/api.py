from fastapi import APIRouter, Depends, HTTPException

from app.db import get_db
from app.models import Connector, PlatformPolicy, TradeLog, User, UserPlatformGrant
from app.routers.deps import admin_user, current_user
from app.schemas import (
    AdminUserCreate,
    AdminGrantUpdate,
    AdminPolicyUpdate,
    AdminUserUpdate,
    ConnectorCreate,
    ConnectorUpdate,
    StrategyRequest,
    TradingViewWebhook,
)
from app.security import encrypt_payload, hash_password
from app.services.connectors import get_client
from app.services.policies import ensure_user_grants, get_user_grant, validate_connector_request
from app.services.trading import dashboard_data, run_strategy

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/me")
def me(user=Depends(current_user), db=Depends(get_db)):
    ensure_user_grants(db, user)
    return {"id": user.id, "email": user.email, "name": user.name, "is_admin": user.is_admin}


@router.put("/me")
def me_update(payload: dict, db=Depends(get_db), user=Depends(current_user)):
    next_name = payload.get("name")
    if next_name is not None:
        clean_name = str(next_name).strip()
        if len(clean_name) < 2 or len(clean_name) > 255:
            raise HTTPException(status_code=400, detail="Name must be between 2 and 255 characters")
        user.name = clean_name
    db.commit()
    return {"ok": True, "id": user.id, "name": user.name}


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
def create_connector(payload: ConnectorCreate, db=Depends(get_db), user: User = Depends(admin_user)):
    target_user_id = payload.user_id or user.id
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
def update_connector(connector_id: int, payload: ConnectorUpdate, db=Depends(get_db), user: User = Depends(admin_user)):
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

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
        connector.config_json = payload.config
    if payload.secrets is not None:
        connector.encrypted_secret_blob = encrypt_payload(payload.secrets)
    if payload.is_enabled is not None:
        connector.is_enabled = payload.is_enabled
    db.commit()
    return {"ok": True}


@router.delete("/connectors/{connector_id}")
def delete_connector(connector_id: int, db=Depends(get_db), user: User = Depends(admin_user)):
    connector = db.query(Connector).filter(Connector.id == connector_id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
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
    result = run_strategy(
        db=db,
        user_id=user.id,
        connector_ids=payload.connector_ids,
        symbols=payload.symbols,
        timeframe=payload.timeframe,
        strategy_slug=payload.strategy_slug,
        risk_per_trade=payload.risk_per_trade,
        min_ml_probability=payload.min_ml_probability,
        use_live_if_available=payload.use_live_if_available,
    )
    return {"ok": True, "results": result}


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
def admin_update_user(user_id: int, payload: AdminUserUpdate, db=Depends(get_db), _: User = Depends(admin_user)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.is_admin is not None:
        user.is_admin = payload.is_admin
    db.commit()
    return {"ok": True}


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
