from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def _load_connectors_module():
    app_module = types.ModuleType("app")
    security_module = types.ModuleType("app.security")
    security_module.decrypt_payload = lambda payload: payload or {}
    app_module.security = security_module

    httpx_module = types.ModuleType("httpx")
    httpx_module.Client = object

    sys.modules["app"] = app_module
    sys.modules["app.security"] = security_module
    sys.modules["httpx"] = httpx_module

    module_path = Path(__file__).resolve().parents[1] / "app" / "services" / "connectors.py"
    spec = importlib.util.spec_from_file_location("connectors_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _FakeExchange:
    def __init__(self, kwargs=None):
        self.kwargs = kwargs or {}

    def load_markets(self):
        return {
            "ETH/USDT": {
                "id": "ETHUSDT",
                "base": "ETH",
                "quote": "USDT",
                "limits": {
                    "cost": {"min": 100.0},
                    "amount": {"min": 0.001},
                    "price": {"min": 0.01},
                },
                "precision": {"amount": 3, "price": 2},
            }
        }

    def amount_to_precision(self, symbol, quantity):
        return f"{float(quantity):.3f}"

    def price_to_precision(self, symbol, price):
        return f"{float(price):.2f}"

    def create_order(self, **kwargs):
        raise Exception("ReduceOnly Order is rejected")


class _FakeConnector:
    platform = "binance"
    mode = "live"
    market_type = "futures"
    encrypted_secret_blob = {}
    config_json = {}


class _FakeLiveSignalConnector:
    platform = "tradingview"
    mode = "live"
    market_type = "spot"
    encrypted_secret_blob = {}
    config_json = {}


def test_pretrade_validate_keeps_risk_sized_quantity_when_below_min_notional():
    connectors = _load_connectors_module()
    connectors.ccxt = types.SimpleNamespace(binance=_FakeExchange)

    client = connectors.CCXTConnectorClient(_FakeConnector())

    result = client.pretrade_validate("ETH/USDT", quantity=0.01, price_hint=1000.0)

    assert result["ok"] is False
    assert result["reason_code"] == "skipped_min_notional"
    assert result["normalized_quantity"] == 0.01
    assert result["exchange_filters"]["required_min_qty_for_notional"] == 0.1
    assert result["exchange_filters"]["projected_notional"] == 10.0


def test_execute_market_surfaces_rejection_category_and_payload_details():
    connectors = _load_connectors_module()
    connectors.ccxt = types.SimpleNamespace(binance=_FakeExchange)

    client = connectors.CCXTConnectorClient(_FakeConnector())

    try:
        client.execute_market(
            symbol="ETH/USDT",
            side="sell",
            quantity=0.1,
            price_hint=2500.0,
            reduce_only=True,
        )
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected a RuntimeError for the rejected exchange order")

    assert "market_order rejected by exchange" in message
    assert "category=reduce_only_rejected" in message
    assert "symbol=ETH/USDT" in message
    assert "side=sell" in message
    assert "reduce_only=true" in message
    assert "params={'reduceOnly': True}" in message


def test_live_signal_connectors_do_not_fallback_to_demo_balance():
    connectors = _load_connectors_module()

    client = connectors.TradingViewConnectorClient(_FakeLiveSignalConnector())
    result = client.fetch_available_balance()

    assert result["ok"] is False
    assert result["source"] == "signal_only_connector"
    assert result["available_balance"] == 0.0
    assert result["total_balance"] == 0.0


def test_mt5_live_balance_comes_from_account_info_not_demo_hint():
    connectors = _load_connectors_module()

    class _FakeMT5:
        @staticmethod
        def initialize(path=None):
            return True

        @staticmethod
        def login(login=None, password=None, server=None):
            return True

        @staticmethod
        def shutdown():
            return True

        @staticmethod
        def account_info():
            return types.SimpleNamespace(
                currency="USD",
                margin_free=742.5,
                equity=801.2,
                balance=790.0,
                login=123456,
                server="Demo-Server",
            )

        @staticmethod
        def last_error():
            return (0, "ok")

    class _FakeMT5Connector:
        platform = "mt5"
        mode = "live"
        market_type = "futures"
        encrypted_secret_blob = {"login": "123456", "password": "secret", "server": "Demo-Server"}
        config_json = {}

    connectors.mt5 = _FakeMT5
    client = connectors.MT5ConnectorClient(_FakeMT5Connector())

    result = client.fetch_available_balance()

    assert result["ok"] is True
    assert result["source"] == "mt5_account_info"
    assert result["available_balance"] == 742.5
    assert result["total_balance"] == 801.2
    assert result["quote_asset"] == "USD"
