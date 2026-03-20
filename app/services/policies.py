from __future__ import annotations

from fastapi import HTTPException

from app.models import Connector, PlatformPolicy, TradeLog, User, UserPlatformGrant

DEFAULT_POLICIES = {
    "mt5": {
        "display_name": "MetaTrader 5",
        "category": "broker",
        "top_symbols": ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "US30", "NAS100", "BTCUSD", "ETHUSD", "AUDUSD", "USDCAD"],
        "allow_manual_symbols": True,
        "guide": {
            "title": "Conectar MetaTrader 5",
            "summary": "Necesitas el terminal MT5 instalado, una cuenta del broker y los datos de login/servidor.",
            "fields_needed": ["login", "password", "server", "terminal_path opcional"],
            "steps": [
                "Instala MetaTrader 5 en la máquina donde corre esta app.",
                "Abre el terminal y verifica que la cuenta del broker inicia sesión correctamente.",
                "Copia el nombre exacto del servidor del broker y tu número de login.",
                "En la app crea el conector MT5 y pega login, password y server.",
                "Si hace falta, indica terminal_path con la ruta del ejecutable terminal64.exe.",
                "Pulsa Test para validar conexión antes de operar en live."
            ]
        },
    },
    "ctrader": {
        "display_name": "cTrader",
        "category": "broker",
        "top_symbols": ["EURUSD", "GBPUSD", "XAUUSD", "US30", "NAS100", "BTCUSD", "ETHUSD", "USDJPY", "AUDUSD", "GER40"],
        "allow_manual_symbols": True,
        "guide": {
            "title": "Conectar cTrader",
            "summary": "Esta base usa bridge_url para hablar con un servicio bridge tuyo o un cliente Open API.",
            "fields_needed": ["client_id", "client_secret", "access_token", "account_id", "bridge_url"],
            "steps": [
                "Crea tu aplicación en el portal Open API de cTrader.",
                "Obtén client_id y client_secret.",
                "Autoriza la app y guarda access_token y account_id.",
                "Levanta un bridge propio que exponga /health y /execute.",
                "Crea el conector en esta app y pega bridge_url y las credenciales.",
                "Usa Test para verificar que el bridge responde antes del live."
            ]
        },
    },
    "tradingview": {
        "display_name": "TradingView",
        "category": "signals",
        "top_symbols": ["BTCUSDT", "ETHUSDT", "EURUSD", "XAUUSD", "SPX", "NDQ", "SOLUSDT", "BNBUSDT", "AAPL", "TSLA"],
        "allow_manual_symbols": True,
        "guide": {
            "title": "Conectar TradingView",
            "summary": "TradingView no ejecuta por sí solo; manda una alerta webhook a esta app y desde aquí se reenvía a otro conector.",
            "fields_needed": ["passphrase opcional", "connector_id", "target_connector_id opcional"],
            "steps": [
                "Crea el conector TradingView y define una passphrase si quieres validar el webhook.",
                "En TradingView crea una alerta desde tu script o estrategia.",
                "Activa Webhook URL y apunta a /api/webhooks/tradingview de tu backend.",
                "En el mensaje JSON incluye connector_id, symbol, side, price y opcionalmente target_connector_id.",
                "Dispara una alerta de prueba y revisa la bitácora en el dashboard."
            ]
        },
    },
    "binance": {
        "display_name": "Binance",
        "category": "crypto",
        "top_symbols": ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT", "ADA/USDT", "DOGE/USDT", "AVAX/USDT", "LINK/USDT", "LTC/USDT"],
        "allow_manual_symbols": True,
        "guide": {
            "title": "Conectar Binance",
            "summary": "Necesitas API key y secret key del usuario, idealmente con permisos de lectura y trade, no de retiro.",
            "fields_needed": ["api_key", "secret_key"],
            "steps": [
                "Inicia sesión en Binance y entra a Account / API Management.",
                "Crea una nueva API y completa 2FA.",
                "Guarda la API key y la Secret key; la secret solo se muestra al crearla.",
                "Desactiva retiros y deja solo permisos mínimos necesarios.",
                "Si quieres, limita IPs en Binance para más seguridad.",
                "Pega api_key y secret_key en este conector y usa Test antes de activar live."
            ]
        },
    },
    "bybit": {
        "display_name": "Bybit",
        "category": "crypto",
        "top_symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "ADA/USDT", "DOGE/USDT", "LINK/USDT", "LTC/USDT", "BNB/USDT", "AVAX/USDT"],
        "allow_manual_symbols": True,
        "guide": {
            "title": "Conectar Bybit",
            "summary": "Usa API key de tipo HMAC o RSA según tu flujo. Para esta base, la forma práctica es API key y secret key.",
            "fields_needed": ["api_key", "secret_key"],
            "steps": [
                "Inicia sesión en Bybit y entra al panel API.",
                "Crea una API key del tipo que prefieras; esta app usa bien el formato api_key + secret_key.",
                "Asigna permisos mínimos necesarios para lectura y trade.",
                "Desactiva retiros y configura whitelist de IP si tu operación lo permite.",
                "Guarda api_key y secret_key en el conector.",
                "Ejecuta Test antes de poner el conector en live."
            ]
        },
    },
    "okx": {
        "display_name": "OKX",
        "category": "crypto",
        "top_symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT", "ADA/USDT", "LTC/USDT", "BNB/USDT", "LINK/USDT", "AVAX/USDT"],
        "allow_manual_symbols": True,
        "guide": {
            "title": "Conectar OKX",
            "summary": "OKX requiere api_key, secret_key y passphrase. La passphrase la define el usuario al crear la clave.",
            "fields_needed": ["api_key", "secret_key", "passphrase"],
            "steps": [
                "Inicia sesión en OKX y abre la sección API.",
                "Crea una API key y define una passphrase que debes recordar.",
                "Guarda api_key, secret_key y passphrase; si pierdes la passphrase debes generar una nueva API.",
                "Configura permisos mínimos y desactiva retiros.",
                "Opcionalmente limita IPs para mayor seguridad.",
                "Pega los 3 datos en el conector y prueba conexión."
            ]
        },
    },
}


def seed_platform_policies(db):
    for platform, data in DEFAULT_POLICIES.items():
        policy = db.query(PlatformPolicy).filter(PlatformPolicy.platform == platform).first()
        if not policy:
            policy = PlatformPolicy(
                platform=platform,
                display_name=data["display_name"],
                category=data["category"],
                is_enabled_global=True,
                allow_manual_symbols=data["allow_manual_symbols"],
                top_symbols_json={"symbols": data["top_symbols"]},
                allowed_symbols_json={"symbols": []},
                guide_json=data["guide"],
            )
            db.add(policy)
    db.commit()


def ensure_user_grants(db, user: User):
    policies = db.query(PlatformPolicy).all()
    for policy in policies:
        grant = db.query(UserPlatformGrant).filter(
            UserPlatformGrant.user_id == user.id,
            UserPlatformGrant.platform == policy.platform,
        ).first()
        if not grant:
            db.add(UserPlatformGrant(
                user_id=user.id,
                platform=policy.platform,
                is_enabled=True,
                max_symbols=5,
                max_daily_movements=25,
                notes="Auto-created default grant",
            ))
    db.commit()


def get_user_grant(db, user_id: int, platform: str) -> UserPlatformGrant | None:
    return db.query(UserPlatformGrant).filter(
        UserPlatformGrant.user_id == user_id,
        UserPlatformGrant.platform == platform,
    ).first()


def validate_connector_request(db, user: User, platform: str, symbols: list[str], connector_id: int | None = None):
    policy = db.query(PlatformPolicy).filter(PlatformPolicy.platform == platform).first()
    if not policy or not policy.is_enabled_global:
        raise HTTPException(status_code=403, detail=f"Platform {platform} is disabled by admin")

    grant = get_user_grant(db, user.id, platform)
    if not grant or not grant.is_enabled:
        raise HTTPException(status_code=403, detail=f"Platform {platform} is not enabled for this user")

    if len(symbols) > grant.max_symbols:
        raise HTTPException(status_code=400, detail=f"This account can use at most {grant.max_symbols} symbols on {platform}")


    day_count = db.query(TradeLog).join(Connector, TradeLog.connector_id == Connector.id).filter(
        TradeLog.user_id == user.id,
        Connector.platform == platform,
    ).count()
    if connector_id is None and day_count > grant.max_daily_movements * 10:
        # soft heuristic guard for demo app
        raise HTTPException(status_code=400, detail=f"Movement history on {platform} is above demo guard threshold; review admin limits")

    return policy, grant
