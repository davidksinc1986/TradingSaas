from __future__ import annotations

import importlib.util
import sys
import types
from datetime import datetime, timedelta
from pathlib import Path


class _Field:
    def __eq__(self, _other):
        return self

    def is_(self, _other):
        return self


class _BaseModel:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        if not hasattr(self, "meta_json"):
            self.meta_json = {}


class OpenPosition(_BaseModel):
    connector_id = _Field()
    is_open = _Field()



class TradeLog(_BaseModel):
    pass


class Connector(_BaseModel):
    id = _Field()
    is_enabled = _Field()



class TradeRun(_BaseModel):
    pass


class User(_BaseModel):
    pass


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeDB:
    def __init__(self, connectors=None, positions=None):
        self.connectors = list(connectors or [])
        self.positions = list(positions or [])
        self.added = []
        self.flushed = 1000

    def query(self, model):
        name = getattr(model, "__name__", str(model))
        if name == "Connector":
            return _FakeQuery(self.connectors)
        if name == "OpenPosition":
            return _FakeQuery(self.positions)
        return _FakeQuery([])

    def add(self, obj):
        self.added.append(obj)
        if obj.__class__.__name__ == "OpenPosition" and obj not in self.positions:
            self.positions.append(obj)

    def flush(self):
        for obj in self.added:
            if obj.__class__.__name__ == "OpenPosition" and getattr(obj, "id", None) in (None, 0):
                self.flushed += 1
                obj.id = self.flushed

    def commit(self):
        return None


def _load_position_lifecycle_module():
    app_module = types.ModuleType("app")
    models_module = types.ModuleType("app.models")
    connectors_module = types.ModuleType("app.services.connectors")
    market_module = types.ModuleType("app.services.market")
    strategies_module = types.ModuleType("app.services.strategies")
    services_module = types.ModuleType("app.services")
    sqlalchemy_module = types.ModuleType("sqlalchemy")
    sqlalchemy_orm_module = types.ModuleType("sqlalchemy.orm")

    models_module.Connector = Connector
    models_module.OpenPosition = OpenPosition
    models_module.TradeLog = TradeLog
    models_module.TradeRun = TradeRun
    models_module.User = User

    class BaseConnectorClient:
        pass

    connectors_module.BaseConnectorClient = BaseConnectorClient
    connectors_module.get_client = lambda connector: None
    market_module.fetch_ohlcv_frame = lambda **kwargs: types.SimpleNamespace(frame=types.SimpleNamespace(empty=True), meta={})
    strategies_module.STRATEGY_MAP = {}

    sqlalchemy_orm_module.Session = object
    sqlalchemy_module.orm = sqlalchemy_orm_module

    app_module.models = models_module
    app_module.services = services_module
    services_module.connectors = connectors_module
    services_module.market = market_module
    services_module.strategies = strategies_module

    sys.modules["app"] = app_module
    sys.modules["app.models"] = models_module
    sys.modules["app.services"] = services_module
    sys.modules["app.services.connectors"] = connectors_module
    sys.modules["app.services.market"] = market_module
    sys.modules["app.services.strategies"] = strategies_module
    sys.modules["sqlalchemy"] = sqlalchemy_module
    sys.modules["sqlalchemy.orm"] = sqlalchemy_orm_module

    module_path = Path(__file__).resolve().parents[1] / "app" / "services" / "position_lifecycle.py"
    spec = importlib.util.spec_from_file_location("position_lifecycle_under_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _RetryingClient:
    def __init__(self):
        self.fetch_calls = 0
        self.execute_calls = 0

    def fetch_position_context(self, symbol: str):
        self.fetch_calls += 1
        if self.fetch_calls in {1, 2}:
            return {"symbol": symbol, "has_position": True, "net_contracts": 1.0, "side": "long", "mark_price": 101.0}
        if self.fetch_calls == 3:
            return {"symbol": symbol, "has_position": True, "net_contracts": 1.0, "side": "long", "mark_price": 100.5}
        return {"symbol": symbol, "has_position": False, "net_contracts": 0.0, "side": None, "mark_price": 100.0}

    def execute_market(self, **kwargs):
        self.execute_calls += 1
        return types.SimpleNamespace(
            status="live-filled",
            fill_price=100.0,
            quantity=kwargs["quantity"],
            raw={"attempt": self.execute_calls, **kwargs},
        )

    def list_open_positions(self, symbols=None):
        return []


class _ReconcileClient:
    def list_open_positions(self, symbols=None):
        return [
            {
                "symbol": "BTC/USDT",
                "has_position": True,
                "net_contracts": 0.5,
                "side": "long",
                "entry_price": 60000.0,
                "mark_price": 60100.0,
                "spot_base_total": 0.0,
            }
        ]

    def fetch_position_context(self, symbol: str):
        return {"symbol": symbol, "has_position": False, "net_contracts": 0.0, "spot_base_total": 0.0, "side": None}


def _connector(**kwargs):
    payload = {
        "id": 7,
        "user_id": 3,
        "platform": "binance",
        "label": "Main",
        "mode": "live",
        "market_type": "futures",
        "symbols_json": {"symbols": ["BTC/USDT"]},
        "config_json": {},
        "encrypted_secret_blob": {},
        "is_enabled": True,
    }
    payload.update(kwargs)
    return Connector(**payload)


def test_validate_exit_policy_requires_hard_stop_and_fallback():
    lifecycle = _load_position_lifecycle_module()

    ok, errors = lifecycle.validate_exit_policy(
        {
            "stop_loss": {"enabled": False, "value": 0},
            "take_profit": {"enabled": False, "value": 0},
            "trailing_stop": {"enabled": False, "value": 0},
            "fallback_exit": {"timeout_minutes": 0, "max_drawdown_pct": 0},
        }
    )

    assert ok is False
    assert set(errors) == {"missing_stop_loss", "missing_profit_capture_mechanism", "missing_fallback_exit"}


def test_evaluate_exit_conditions_triggers_trailing_stop_and_timeout():
    lifecycle = _load_position_lifecycle_module()
    position = OpenPosition(
        id=1,
        user_id=1,
        connector_id=1,
        platform="binance",
        market_type="futures",
        symbol="BTC/USDT",
        position_side="long",
        entry_price=100.0,
        current_qty=1.0,
        is_open=True,
        opened_at=datetime.utcnow() - timedelta(minutes=300),
        meta_json={
            "stop_loss_price": 95.0,
            "take_profit_price": 110.0,
            "trailing_stop_value": 2.0,
            "peak_price": 108.0,
        },
    )
    lifecycle.initialize_position_lifecycle(
        position,
        strategy_slug="ema_rsi",
        timeframe="5m",
        take_profit_mode="percent",
        take_profit_value=10,
        stop_loss_mode="percent",
        stop_loss_value=5,
        trailing_stop_mode="percent",
        trailing_stop_value=2,
        indicator_exit_enabled=False,
        indicator_exit_rule="macd_cross",
        timeout_minutes=240,
    )
    position.meta_json["peak_price"] = 108.0

    trailing = lifecycle.evaluate_exit_conditions(position, {"price": 105.5, "signal": "hold"}, {"now": datetime.utcnow()})
    timeout = lifecycle.evaluate_exit_conditions(position, {"price": 109.0, "signal": "hold"}, {"now": datetime.utcnow() + timedelta(minutes=1)})

    assert trailing["should_close"] is True
    assert trailing["reason"] == "trailing_stop"
    assert timeout["should_close"] is True
    assert timeout["reason"] == "timeout"


def test_execute_close_position_retries_until_exchange_confirms_zero_size():
    lifecycle = _load_position_lifecycle_module()
    connector = _connector()
    position = OpenPosition(
        id=11,
        user_id=connector.user_id,
        connector_id=connector.id,
        platform=connector.platform,
        market_type=connector.market_type,
        symbol="BTC/USDT",
        position_side="long",
        entry_price=100.0,
        current_qty=1.0,
        is_open=True,
        opened_at=datetime.utcnow() - timedelta(minutes=20),
        meta_json={"stop_loss_price": 95.0, "take_profit_price": 110.0},
    )
    position.connector = connector
    lifecycle.initialize_position_lifecycle(
        position,
        strategy_slug="ema_rsi",
        timeframe="5m",
        take_profit_mode="percent",
        take_profit_value=10,
        stop_loss_mode="percent",
        stop_loss_value=5,
        trailing_stop_mode="percent",
        trailing_stop_value=1,
        indicator_exit_enabled=False,
        indicator_exit_rule="macd_cross",
    )
    db = _FakeDB(connectors=[connector], positions=[position])
    client = _RetryingClient()

    result = lifecycle.execute_close_position(db, position, reason="risk", urgency="critical", client=client)

    assert result["closed"] is True
    assert client.execute_calls == 2
    assert position.is_open is False
    assert any(item.__class__.__name__ == "TradeLog" for item in db.added)
    assert position.meta_json["lifecycle"]["state"] == "closed"


def test_reconcile_positions_creates_orphan_record():
    lifecycle = _load_position_lifecycle_module()
    connector = _connector()
    db = _FakeDB(connectors=[connector], positions=[])
    lifecycle.get_client = lambda _connector: _ReconcileClient()

    result = lifecycle.reconcile_positions_with_exchange(db, connector, close_orphans=False)

    assert len(result["orphaned"]) == 1
    orphan = db.positions[0]
    assert orphan.symbol == "BTC/USDT"
    assert orphan.meta_json["lifecycle"]["state"] == "orphaned"
    assert orphan.meta_json["created_by_reconciliation"] is True
