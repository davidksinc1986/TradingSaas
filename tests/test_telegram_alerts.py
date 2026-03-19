from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def _load_alerts_module():
    app_module = types.ModuleType("app")
    core_module = types.ModuleType("app.core")
    core_module.settings = types.SimpleNamespace(
        telegram_admin_bot_token="",
        telegram_admin_chat_id="",
    )
    models_module = types.ModuleType("app.models")

    class User:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    models_module.User = User

    security_module = types.ModuleType("app.security")
    security_module.decrypt_payload = lambda payload: payload or {}

    httpx_module = types.ModuleType("httpx")
    httpx_module.Client = object
    httpx_module.AsyncClient = object

    app_module.core = core_module
    app_module.models = models_module
    app_module.security = security_module

    sys.modules["app"] = app_module
    sys.modules["app.core"] = core_module
    sys.modules["app.models"] = models_module
    sys.modules["app.security"] = security_module
    sys.modules["httpx"] = httpx_module

    module_path = Path(__file__).resolve().parents[1] / "app" / "services" / "alerts.py"
    spec = importlib.util.spec_from_file_location("alerts_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _user(**kwargs):
    defaults = {
        "id": 7,
        "email": "telegram@example.com",
        "name": "Telegram User",
        "telegram_alerts_enabled": True,
        "telegram_bot_token_encrypted": {"value": "123:abc"},
        "telegram_chat_id_encrypted": {"value": "999"},
        "alert_language": "es",
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def test_send_user_telegram_test_alert_posts_message():
    alerts = _load_alerts_module()
    captured = {}

    class _FakeResponse:
        status_code = 200
        text = '{"ok":true}'

        def json(self):
            return {"ok": True}

    class _FakeClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json):
            captured["url"] = url
            captured["json"] = json
            return _FakeResponse()

    alerts.httpx.Client = _FakeClient

    ok = alerts.send_user_telegram_test_alert(_user())

    assert ok is True
    assert captured["url"] == "https://api.telegram.org/bot123:abc/sendMessage"
    assert captured["json"]["chat_id"] == "999"
    assert "Telegram" in captured["json"]["text"]


def test_send_user_telegram_test_alert_raises_clear_error_for_not_found():
    alerts = _load_alerts_module()

    class _FakeResponse:
        status_code = 404
        text = '{"ok":false,"description":"Not Found"}'

        def json(self):
            return {"ok": False, "description": "Not Found"}

    class _FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json):
            return _FakeResponse()

    alerts.httpx.Client = _FakeClient

    try:
        alerts.send_user_telegram_test_alert(_user(), raise_on_error=True)
    except alerts.TelegramDeliveryError as exc:
        assert "404" in str(exc)
        assert "token" in str(exc).lower()
    else:
        raise AssertionError("Expected TelegramDeliveryError for invalid bot token")


def test_send_user_telegram_test_alert_raises_clear_error_for_chat_not_found():
    alerts = _load_alerts_module()

    class _FakeResponse:
        status_code = 400
        text = '{"ok":false,"description":"Bad Request: chat not found"}'

        def json(self):
            return {"ok": False, "description": "Bad Request: chat not found"}

    class _FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json):
            return _FakeResponse()

    alerts.httpx.Client = _FakeClient

    try:
        alerts.send_user_telegram_test_alert(_user(), raise_on_error=True)
    except alerts.TelegramDeliveryError as exc:
        assert "chat not found" in str(exc).lower()
        assert "/start" in str(exc)
    else:
        raise AssertionError("Expected TelegramDeliveryError for invalid chat id")


def test_execution_message_includes_realized_pnl_and_close_reason():
    alerts = _load_alerts_module()

    message = alerts.format_user_execution_message(
        locale="es",
        connector_label="Cuenta principal",
        platform="binance",
        symbol="BTC/USDT",
        side="sell",
        quantity=0.25,
        fill_price=62000.0,
        status="filled",
        strategy_slug="ema_rsi",
        message="Take profit alcanzado",
        pnl=42.5,
        close_reason="take_profit",
    )

    assert "PnL realizado: 42.50000000" in message
    assert "Motivo de cierre: take_profit" in message


def test_user_has_telegram_config_requires_enablement_and_credentials():
    alerts = _load_alerts_module()

    assert alerts.user_has_telegram_config(_user()) is True
    assert alerts.user_has_telegram_config(_user(telegram_alerts_enabled=False)) is False
    assert alerts.user_has_telegram_config(_user(telegram_bot_token_encrypted={})) is False
    assert alerts.user_has_telegram_config(_user(telegram_chat_id_encrypted={})) is False


def test_send_admin_user_alert_sync_wraps_user_context(monkeypatch):
    alerts = _load_alerts_module()
    captured = {}

    def _fake_send(message):
        captured["message"] = message
        return True

    monkeypatch.setattr(alerts, "send_telegram_alert_sync", _fake_send)

    ok = alerts.send_admin_user_alert_sync(_user(name="Admin Routed User"), "Evento importante", scope="execution-ok")

    assert ok is True
    assert "Admin Routed User" in captured["message"]
    assert "execution-ok" in captured["message"]
    assert "Evento importante" in captured["message"]
