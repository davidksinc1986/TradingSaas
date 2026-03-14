from fastapi.testclient import TestClient

from app.main import app
from app.schemas import ConnectorCreate, TradingViewWebhook
from app.security import decrypt_payload, encrypt_payload
from app import security


def test_schema_defaults_are_not_shared_mutable_objects():
    first = ConnectorCreate(platform="binance", label="A")
    second = ConnectorCreate(platform="binance", label="B")

    first.symbols.append("BTC/USDT")
    first.config["mode"] = "x"
    first.secrets["k"] = "v"

    assert second.symbols == []
    assert second.config == {}
    assert second.secrets == {}

    webhook_a = TradingViewWebhook(connector_id=1, symbol="BTCUSDT", side="buy", price=1)
    webhook_b = TradingViewWebhook(connector_id=2, symbol="ETHUSDT", side="sell", price=2)
    webhook_a.extra["note"] = "changed"
    assert webhook_b.extra == {}


def test_encrypt_payload_works_with_fallback_key(monkeypatch):
    monkeypatch.setattr(security.settings, "credentials_key", "replace-with-32-url-safe-base64-key")
    monkeypatch.setattr(security.settings, "secret_key", "my-test-secret")

    blob = encrypt_payload({"api_key": "abc"})
    assert decrypt_payload(blob) == {"api_key": "abc"}


def test_invalid_cookie_format_is_rejected():
    client = TestClient(app)
    response = client.get("/api/me", cookies={"access_token": "token-without-bearer"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token format"


def test_schema_migration_adds_missing_legacy_columns(monkeypatch, tmp_path):
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.orm import sessionmaker

    from app import main as app_main

    legacy_db = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{legacy_db}", connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(255))"))
        conn.execute(text("CREATE TABLE connectors (id INTEGER PRIMARY KEY, user_id INTEGER, platform VARCHAR(50), label VARCHAR(100), mode VARCHAR(20), is_enabled BOOLEAN, symbols_json JSON, config_json JSON, encrypted_secret_blob TEXT, created_at DATETIME)"))
        conn.execute(text("CREATE TABLE bot_sessions (id INTEGER PRIMARY KEY, user_id INTEGER, connector_id INTEGER, strategy_slug VARCHAR(100), timeframe VARCHAR(20), symbols_json JSON, interval_minutes INTEGER, risk_per_trade FLOAT, min_ml_probability FLOAT, use_live_if_available BOOLEAN, is_active BOOLEAN, last_run_at DATETIME, next_run_at DATETIME, last_status VARCHAR(30), last_error TEXT, created_at DATETIME, updated_at DATETIME)"))

    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(app_main, "engine", engine)

    db = Session()
    try:
        app_main.ensure_schema_updates(db)
    finally:
        db.close()

    schema = inspect(engine)
    users = {c["name"] for c in schema.get_columns("users")}
    connectors = {c["name"] for c in schema.get_columns("connectors")}
    bot_sessions = {c["name"] for c in schema.get_columns("bot_sessions")}

    assert {"phone", "telegram_bot_token_encrypted", "trade_amount_mode", "trade_balance_percent"}.issubset(users)
    assert "market_type" in connectors
    assert {"take_profit_mode", "take_profit_value", "trailing_stop_mode", "trailing_stop_value", "indicator_exit_enabled", "indicator_exit_rule"}.issubset(bot_sessions)
