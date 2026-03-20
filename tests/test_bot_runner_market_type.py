from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from app.services import bot_runner


class _FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return list(self.rows)

    def first(self):
        return self.rows[0] if self.rows else None


class _FakeDB:
    def __init__(self, session, connector):
        self.session = session
        self.connector = connector
        self.commits = 0

    def query(self, model):
        name = getattr(model, "__name__", "")
        if name == "BotSession":
            return _FakeQuery([self.session])
        if name == "Connector":
            return _FakeQuery([self.connector])
        raise AssertionError(f"Unexpected model {model!r}")

    def commit(self):
        self.commits += 1


def test_execute_due_bot_sessions_keeps_session_market_type_isolated_from_connector(monkeypatch):
    connector = SimpleNamespace(
        id=10,
        user_id=4,
        is_enabled=True,
        market_type="spot",
        config_json={"defaultType": "future", "market_type": "futures"},
    )
    session = SimpleNamespace(
        id=99,
        user_id=4,
        connector_id=10,
        is_active=True,
        next_run_at=None,
        interval_minutes=15,
        market_type="spot",
        symbols_json={"symbols": ["BTC/USDT"], "symbol_source_mode": "manual"},
        timeframe="15m",
        strategy_slug="momentum_breakout",
        risk_per_trade=0.01,
        min_ml_probability=0.55,
        use_live_if_available=True,
        take_profit_mode="percent",
        take_profit_value=1.2,
        stop_loss_mode="percent",
        stop_loss_value=0.6,
        trailing_stop_mode="percent",
        trailing_stop_value=0.4,
        indicator_exit_enabled=False,
        indicator_exit_rule="macd_cross",
        leverage_profile="balanced",
        max_open_positions=1,
        compound_growth_enabled=False,
        atr_volatility_filter_enabled=True,
        last_status=None,
        last_error=None,
        last_run_at=None,
    )
    db = _FakeDB(session, connector)

    monkeypatch.setattr(bot_runner, "run_position_lifecycle", lambda *_args, **_kwargs: None)
    captured = {}

    def _run_strategy(**kwargs):
        captured.update(kwargs)
        return [{"connector_id": kwargs["connector_ids"][0], "status": "ok"}]

    monkeypatch.setattr(bot_runner, "run_strategy", _run_strategy)

    processed = bot_runner.execute_due_bot_sessions(db, now=datetime(2026, 3, 19, 18, 30, 0))

    assert processed == 1
    assert connector.market_type == "spot"
    assert connector.config_json["market_type"] == "futures"
    assert connector.config_json["defaultType"] == "future"
    assert session.market_type == "spot"
    assert captured["market_type"] == "spot"
    assert session.last_status == "ok"


def test_execute_due_bot_sessions_uses_connector_sizing_when_session_inherits(monkeypatch):
    connector = SimpleNamespace(
        id=11,
        user_id=4,
        is_enabled=True,
        market_type="futures",
        config_json={"market_type": "futures", "trade_amount_mode": "fixed_usd", "fixed_trade_amount_usd": 50},
    )
    session = SimpleNamespace(
        id=100,
        user_id=4,
        connector_id=11,
        is_active=True,
        next_run_at=None,
        interval_minutes=15,
        market_type="futures",
        symbols_json={"symbols": ["BTC/USDT"], "symbol_source_mode": "manual"},
        timeframe="15m",
        strategy_slug="momentum_breakout",
        risk_per_trade=0.01,
        trade_amount_mode="inherit",
        amount_per_trade=None,
        amount_percentage=None,
        min_ml_probability=0.55,
        use_live_if_available=True,
        take_profit_mode="percent",
        take_profit_value=1.2,
        stop_loss_mode="percent",
        stop_loss_value=0.6,
        trailing_stop_mode="percent",
        trailing_stop_value=0.4,
        indicator_exit_enabled=False,
        indicator_exit_rule="macd_cross",
        leverage_profile="balanced",
        max_open_positions=1,
        compound_growth_enabled=False,
        atr_volatility_filter_enabled=True,
        last_status=None,
        last_error=None,
        last_run_at=None,
    )
    db = _FakeDB(session, connector)

    monkeypatch.setattr(bot_runner, "run_position_lifecycle", lambda *_args, **_kwargs: None)
    captured = {}

    def _run_strategy(**kwargs):
        captured.update(kwargs)
        return [{"connector_id": kwargs["connector_ids"][0], "status": "ok"}]

    monkeypatch.setattr(bot_runner, "run_strategy", _run_strategy)

    processed = bot_runner.execute_due_bot_sessions(db, now=datetime(2026, 3, 19, 18, 30, 0))

    assert processed == 1
    assert captured["trade_amount_mode"] == "inherit"
    assert captured["fixed_trade_amount_usd"] is None
    assert session.last_status == "ok"
