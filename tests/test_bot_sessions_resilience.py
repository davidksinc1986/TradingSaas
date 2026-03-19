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
        self.flushed = 0
        self.commits = 0

    def query(self, *_args, **_kwargs):
        return _FakeQuery(self._sessions)

    def add(self, obj):
        self._sessions.append(obj)

    def flush(self):
        self.flushed += 1
        for index, item in enumerate(self._sessions, start=1):
            if getattr(item, "id", None) is None:
                item.id = index

    def commit(self):
        self.commits += 1


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


def test_list_bot_sessions_keeps_explicit_session_market_type(monkeypatch):
    connector = SimpleNamespace(
        id=44,
        label="Cuenta Binance Futures",
        platform="binance",
        mode="live",
        market_type="spot",
        config_json={"defaultType": "future", "market_type": "futures"},
    )
    session = SimpleNamespace(
        id=21,
        connector_id=44,
        connector=connector,
        user=SimpleNamespace(fixed_trade_amount_usd=10),
        strategy_slug="momentum_breakout",
        timeframe="15m",
        symbols_json={"symbols": ["BTC/USDT"]},
        interval_minutes=15,
        risk_per_trade=0.01,
        min_ml_probability=0.55,
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
        is_active=True,
        last_run_at=None,
        next_run_at=None,
        last_status="queued",
        last_error=None,
        created_at=None,
        market_type="futures",
    )

    rows = api.list_bot_sessions(db=_FakeDB([session]), user=SimpleNamespace(id=7))

    assert rows[0]["market_type"] == "futures"


def test_list_bot_sessions_does_not_overwrite_session_market_type_from_connector_defaults(monkeypatch):
    connector = SimpleNamespace(
        id=45,
        label="Cuenta Binance Futures",
        platform="binance",
        mode="live",
        market_type="spot",
        config_json={"defaultType": "future", "market_type": "futures"},
    )
    session = SimpleNamespace(
        id=22,
        connector_id=45,
        connector=connector,
        user=SimpleNamespace(fixed_trade_amount_usd=10),
        strategy_slug="momentum_breakout",
        timeframe="15m",
        symbols_json={"symbols": ["BTC/USDT"]},
        interval_minutes=15,
        risk_per_trade=0.01,
        min_ml_probability=0.55,
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
        is_active=True,
        last_run_at=None,
        next_run_at=None,
        last_status="queued",
        last_error=None,
        created_at=None,
        market_type="spot",
    )

    rows = api.list_bot_sessions(db=_FakeDB([session]), user=SimpleNamespace(id=7))

    assert rows[0]["market_type"] == "spot"


def test_list_bot_sessions_uses_session_trade_amount_overrides(monkeypatch):
    connector = SimpleNamespace(
        id=46,
        label="Cuenta Bybit",
        platform="bybit",
        mode="live",
        market_type="futures",
        config_json={"market_type": "futures"},
    )
    session = SimpleNamespace(
        id=23,
        connector_id=46,
        connector=connector,
        user=SimpleNamespace(trade_amount_mode="fixed_usd", fixed_trade_amount_usd=10000, trade_balance_percent=12),
        strategy_slug="momentum_breakout",
        timeframe="15m",
        symbols_json={"symbols": ["BTC/USDT"]},
        interval_minutes=15,
        risk_per_trade=0.01,
        trade_amount_mode="balance_percent",
        amount_per_trade=None,
        amount_percentage=3.5,
        min_ml_probability=0.55,
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
        is_active=True,
        last_run_at=None,
        next_run_at=None,
        last_status="queued",
        last_error=None,
        created_at=None,
        market_type="futures",
    )

    rows = api.list_bot_sessions(db=_FakeDB([session]), user=SimpleNamespace(id=7, trade_amount_mode="fixed_usd", fixed_trade_amount_usd=10000, trade_balance_percent=12))

    assert rows[0]["trade_amount_mode"] == "balance_percent"
    assert rows[0]["capital_per_operation"] == 3.5
    assert rows[0]["capital_display_unit"] == "%"


def test_create_bot_session_flushes_and_returns_session_id_without_refresh(monkeypatch):
    connector = SimpleNamespace(
        id=77,
        user_id=5,
        label="Bybit Futures",
        platform="bybit",
        mode="live",
        market_type="futures",
        config_json={"market_type": "futures"},
        is_enabled=True,
    )

    class _CreateQuery:
        def __init__(self, row):
            self.row = row

        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return self.row

    class _CreateDB(_FakeDB):
        def __init__(self, connector_row):
            super().__init__([])
            self.connector_row = connector_row

        def query(self, model, *_args, **_kwargs):
            if getattr(model, "__name__", "") == "Connector":
                return _CreateQuery(self.connector_row)
            return _CreateQuery(None)

    db = _CreateDB(connector)
    notifications = []
    monkeypatch.setattr(api, "_ensure_strategy_control", lambda *_args, **_kwargs: SimpleNamespace(managed_by_admin=False, allowed_strategies_json={"items": api.ALL_STRATEGIES}))
    monkeypatch.setattr(api, "_validate_strategy_connectors", lambda *_args, **_kwargs: [connector])
    monkeypatch.setattr(api, "_notify_user_info", lambda *_args, **_kwargs: notifications.append(True))

    payload = api.BotSessionCreate(
        connector_id=77,
        market_type="futures",
        symbols=["BTC/USDT"],
        timeframe="15m",
        strategy_slug="momentum_breakout",
        risk_per_trade=1,
        trade_amount_mode="fixed_usd",
        amount_per_trade=125,
        min_ml_probability=55,
        interval_minutes=15,
        take_profit_mode="percent",
        take_profit_value=1.2,
        stop_loss_mode="percent",
        stop_loss_value=0.6,
        trailing_stop_mode="percent",
        trailing_stop_value=0.4,
    )

    result = api.create_bot_session(payload=payload, db=db, user=SimpleNamespace(id=5, trade_amount_mode="fixed_usd", fixed_trade_amount_usd=10, trade_balance_percent=10, alert_language="es"))

    assert result["ok"] is True
    assert result["session_id"] == 1
    assert db.flushed == 1
    assert db.commits == 1
    assert notifications


def test_dashboard_returns_safe_payload_when_aggregation_fails(monkeypatch):
    monkeypatch.setattr(api, "dashboard_data", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    alerts = []
    monkeypatch.setattr(api, "_alert_admin_failure", lambda scope, detail: alerts.append((scope, detail)))

    payload = api.dashboard(db=object(), user=SimpleNamespace(id=12))
    assert payload["total_connectors"] == 0
    assert payload["latest_trades"] == []
    assert alerts and alerts[0][0] == "API /api/dashboard"
