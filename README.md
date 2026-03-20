# Multi Market Quant Suite v4

Esta es la reconstrucción descargable de la v4 en ZIP.

## Documento de rediseño

- Propuesta integral de producto, UX, arquitectura funcional y estrategia multilenguaje: `docs/REDISENO_PRODUCTO_UX_ARQUITECTURA.md`
- Blueprint inicial del motor de configuraciones dinámicas: `docs/dynamic_config_blueprint.json`

## Qué incluye

- multiusuario con login (usuarios creados por super user)
- cuenta admin inicial por variables de entorno
- control de usuarios y límites por plataforma
- conectores para MT5, cTrader, TradingView, Binance, Bybit y OKX
- múltiples conectores por usuario en una misma plataforma
- `market_type` por conector, para soportar casos como Binance spot/futures, Bybit spot/futures, OKX spot/futures y MT5/cTrader con forex/cfd donde aplique
- lista de 10 símbolos sugeridos por plataforma
- entrada manual de símbolos
- popup de guía de conexión por plataforma
- dashboard con transacciones y conectores
- webhook TradingView hacia otros conectores

## Qué significa bridge

Un **bridge** es un microservicio intermedio entre esta app y otra plataforma de ejecución.

En esta base se usa sobre todo para **cTrader**:

1. tu SaaS recibe la orden
2. el bridge la traduce al formato que cTrader/Open API necesita
3. el bridge firma/autentica la petición
4. el bridge devuelve el resultado a tu SaaS

## Variables importantes

```env
ADMIN_EMAIL=davidksinc
ADMIN_NAME=davidksinc
ADMIN_PASSWORD=M@davi19!
SECRET_KEY=super-secret-change-me
DATABASE_URL=sqlite:///./quant_suite.db
TELEGRAM_ADMIN_CHAT_ID=6902163541
TELEGRAM_ADMIN_BOT_TOKEN=8550578940:AAFRio825HETZLIbSR22wN8j_xD5u9D_rWA
```

## Modelo operativo actual

- Registro público desactivado: los usuarios los crea el super user.
- Solo super user puede crear/editar/eliminar conectores y límites.
- Usuario final: dashboard de solo lectura para operación y actualización de credenciales del conector (keys/secrets/config técnica).

## Correr local

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

## Notas honestas

- Esta base **no garantiza ganancias**.
- MT5 live requiere el terminal MetaTrader 5 instalado y autenticado.
- cTrader queda **bridge-ready**.
- TradingView no ejecuta órdenes por sí solo; envía alertas webhook a esta app.
