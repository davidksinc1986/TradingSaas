from types import SimpleNamespace

from app.routers import api


class _FakeQuery:
    def __init__(self, sessions):
        self._sessions = sessions

    def outerjoin(self, *_args, **_kwargs):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def all(self):
        return self._sessions


class _FakeDB:
    def __init__(self, sessions):
        self._sessions = sessions

    def query(self, *_args, **_kwargs):
        return _FakeQuery(self._sessions)


class _ExplosiveConnector:
    @property
    def config_json(self):
        raise RuntimeError("config unreadable")


def test_list_bot_sessions_never_returns_500_when_session_is_corrupted(monkeypatch):
    corrupted_session = SimpleNamespace(
        id=999,
        connector_id=123,
        connector=_ExplosiveConnector(),
        strategy_slug="ema_rsi",
        timeframe="5m",
        symbols_json={"symbols": ["BTCUSDT"]},
        interval_minutes=5,
        risk_per_trade=0.01,
        min_ml_probability=0.55,
        take_profit_mode="percent",
        take_profit_value=1.5,
        stop_loss_mode="percent",
        stop_loss_value=1.0,
        trailing_stop_mode="percent",
        trailing_stop_value=0.8,
        indicator_exit_enabled=False,
        indicator_exit_rule="macd_cross",
        is_active=True,
        last_run_at=None,
        next_run_at=None,
        last_status="idle",
        last_error=None,
        created_at=None,
    )

    alerts = []
    monkeypatch.setattr(api, "_alert_admin_failure", lambda scope, detail: alerts.append((scope, detail)))

    result = api.list_bot_sessions(db=_FakeDB([corrupted_session]), user=SimpleNamespace(id=7))

    assert len(result) == 1
    assert result[0]["id"] == 999
    assert result[0]["last_status"] == "error"
    assert "No se pudo serializar" in result[0]["last_error"]
    assert alerts
    assert alerts[0][0] == "API /api/bot-sessions serialization"


def test_safe_float_uses_fallback_for_invalid_values():
    assert api._safe_float("abc", fallback=2.5) == 2.5
    assert api._safe_float(float("nan"), fallback=1.0) == 1.0
    assert api._safe_float("3.25", fallback=0.0) == 3.25


class _ExplosiveConnectorRow:
    def __init__(self):
        self.id = 555
        self.platform = "binance"
        self.label = "B-1"
        self.mode = "paper"
        self.market_type = "spot"
        self.is_enabled = True
        self.created_at = None

    @property
    def symbols_json(self):
        raise RuntimeError("symbols unreadable")


def test_list_connectors_never_returns_500_when_connector_is_corrupted(monkeypatch):
    class _ConnectorQuery:
        def order_by(self, *_args, **_kwargs):
            return self

        def all(self):
            return [_ExplosiveConnectorRow()]

    class _ConnectorDB:
        def query(self, *_args, **_kwargs):
            return self

        def filter(self, *_args, **_kwargs):
            return _ConnectorQuery()

    alerts = []
    monkeypatch.setattr(api, "_alert_admin_failure", lambda scope, detail: alerts.append((scope, detail)))

    rows = api.list_connectors(db=_ConnectorDB(), user=SimpleNamespace(id=9))
    assert len(rows) == 1
    assert rows[0]["id"] == 555
    assert rows[0]["symbols"] == []
    assert alerts and alerts[0][0] == "API /api/connectors serialization"


def test_dashboard_returns_safe_payload_when_aggregation_fails(monkeypatch):
    monkeypatch.setattr(api, "dashboard_data", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    alerts = []
    monkeypatch.setattr(api, "_alert_admin_failure", lambda scope, detail: alerts.append((scope, detail)))

    payload = api.dashboard(db=object(), user=SimpleNamespace(id=12))
    assert payload["total_connectors"] == 0
    assert payload["latest_trades"] == []
    assert alerts and alerts[0][0] == "API /api/dashboard"
