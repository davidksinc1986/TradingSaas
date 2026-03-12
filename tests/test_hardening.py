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
