from __future__ import annotations

import json

import pytest

pd = pytest.importorskip("pandas")
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Connector, OpenPosition, TradeRun, User
from app.services import market as market_module
from app.services import ml as ml_module
from app.services import position_lifecycle as lifecycle_module
from app.services import risk as risk_module
from app.services import risk_engine as risk_engine_module
from app.services import scanner as scanner_module
from app.services import strategies as strategies_module
from app.services import trading
from app.services.market import MarketFrameResult


class _RiskPlan:
    def __init__(self, *, approved: bool = True, approved_qty: float = 1.0, block_reasons: list[str] | None = None):
        self.approved = approved
        self.approved_qty = approved_qty
        self.block_reasons = block_reasons or []
        self.warnings = []

    def to_dict(self):
        return {
            "approved": self.approved,
            "approved_qty": self.approved_qty,
            "block_reasons": list(self.block_reasons),
            "warnings": list(self.warnings),
        }


class _FakeClient:
    def __init__(self, connector, *, position_context, executed_orders):
        self.connector = connector
        self._position_context = position_context
        self.executed_orders = executed_orders

    def normalize_symbol(self, symbol: str):
        return {
            "input_symbol": symbol,
            "normalized_symbol": symbol,
            "exchange_symbol": symbol.replace("/", ""),
            "found": True,
        }

    def fetch_position_context(self, symbol: str):
        return {**self._position_context, "symbol": symbol}

    def fetch_available_balance(self):
        return {
            "ok": True,
            "available_balance": 1000.0,
            "total_balance": 1000.0,
            "quote_asset": "USDT",
            "source": "test_balance",
        }

    def prepare_execution_environment(self, symbol: str, *, leverage_profile: str = "none"):
        config = self.connector.config_json or {}
        resolved_profile = str(leverage_profile or config.get("leverage_profile") or "none").lower()
        explicit_leverage = config.get("futures_leverage")
        if explicit_leverage in (None, ""):
            leverage_map = {"none": 1, "conservative": 2, "balanced": 3, "aggressive": 5}
            explicit_leverage = leverage_map.get(resolved_profile, 1)
        return {
            "ok": True,
            "symbol": symbol,
            "mode": self.connector.mode,
            "market_type": self.connector.market_type,
            "recv_window_ms": int(config.get("recv_window_ms") or 10000),
            "request_timeout_ms": int(config.get("request_timeout_ms") or 20000),
            "retry_attempts": int(config.get("retry_attempts") or 2),
            "retry_delay_ms": int(config.get("retry_delay_ms") or 350),
            "futures_margin_mode": str(config.get("futures_margin_mode") or "isolated"),
            "futures_position_mode": str(config.get("futures_position_mode") or "oneway"),
            "futures_leverage": int(explicit_leverage),
            "leverage_profile": resolved_profile,
            "applied": ["time_sync", f"margin_mode:{config.get('futures_margin_mode') or 'isolated'}"],
            "warnings": [] if self.connector.mode == "live" else ["paper_mode_environment"],
            "capabilities": {"internal_transfer": False, "websocket_market_data": False, "websocket_balance": False},
            "futures_settings": {
                "margin_mode": str(config.get("futures_margin_mode") or "isolated"),
                "position_mode": str(config.get("futures_position_mode") or "oneway"),
                "leverage": int(explicit_leverage),
                "leverage_profile": resolved_profile,
            },
        }

    def resolve_execution_reference_price(self, symbol: str, **kwargs):
        analysis_price = float(kwargs.get("analysis_price") or 0.0)
        return {
            "value": analysis_price,
            "source": "analysis_price",
            "used_fallback": False,
            "details": {"symbol": symbol},
        }

    def pretrade_validate(self, symbol, quantity, price_hint, **kwargs):
        self.executed_orders.append({"stage": "pretrade", "symbol": symbol, "quantity": quantity, "price_hint": price_hint, **kwargs})
        return {
            "ok": True,
            "normalized_quantity": float(quantity),
            "normalized_price": float(price_hint),
            "reason_code": "ok",
            "reason_message": "ok",
            "exchange_filters": {},
        }

    def execute_market(self, *, symbol, side, quantity, price_hint, reduce_only=False, **kwargs):
        self.executed_orders.append({
            "stage": "execute",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price_hint": price_hint,
            "reduce_only": reduce_only,
        })
        return trading.ExecutionResult(
            status="live-filled",
            message="ok",
            fill_price=float(price_hint),
            quantity=float(quantity),
            raw={"symbol": symbol, "side": side, "reduce_only": reduce_only},
        )

    def place_risk_orders(self, **kwargs):
        return {"ok": True, "created": []}


def _make_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def _base_setup(db, *, market_type: str):
    user = User(email=f"{market_type}@test.dev", name="Trader", hashed_password="x", is_active=True, is_admin=False)
    db.add(user)
    db.commit()
    db.refresh(user)

    connector = Connector(
        user_id=user.id,
        platform="binance",
        label=f"Binance {market_type}",
        mode="live",
        market_type=market_type,
        is_enabled=True,
        config_json={
            "recv_window_ms": 8000,
            "request_timeout_ms": 12000,
            "futures_margin_mode": "isolated",
            "futures_position_mode": "oneway",
            "retry_attempts": 4,
            "retry_delay_ms": 125,
        },
        encrypted_secret_blob={},
    )
    db.add(connector)
    db.commit()
    db.refresh(connector)
    return user, connector


def _patch_common(monkeypatch, *, client, market_result, strategy_fn, ml_probability=0.9, approved_qty=1.0):
    monkeypatch.setattr(trading, "ensure_connector_market_type_state", lambda connector, persist=True, db=None: connector.market_type)
    monkeypatch.setattr(trading, "resolve_runtime_market_type", lambda connector, requested_market_type=None: requested_market_type or connector.market_type)
    monkeypatch.setattr(trading, "build_runtime_connector", lambda connector, market_type=None: connector)
    monkeypatch.setattr(trading, "sync_positions_with_exchange", lambda db, connector, symbols=None: {"synced_at": "2026-03-20T00:00:00"})

    monkeypatch.setattr(scanner_module, "select_symbols_for_run", lambda **kwargs: (["BTC/USDT"], {"mode": "manual", "selected_symbols": ["BTC/USDT"]}))
    monkeypatch.setattr(market_module, "fetch_ohlcv_frame", lambda **kwargs: market_result)
    monkeypatch.setattr(ml_module, "train_and_score", lambda data: ml_probability)
    monkeypatch.setattr(risk_module, "position_size", lambda *args, **kwargs: approved_qty)
    monkeypatch.setattr(risk_engine_module, "build_trade_risk_plan", lambda **kwargs: _RiskPlan(approved=True, approved_qty=approved_qty))
    monkeypatch.setattr(lifecycle_module, "run_position_lifecycle", lambda db, connector_ids=None: {"ok": True})
    monkeypatch.setattr(lifecycle_module, "initialize_position_lifecycle", lambda *args, **kwargs: None)
    monkeypatch.setattr(lifecycle_module, "validate_exit_policy", lambda policy: (True, []))
    monkeypatch.setattr(strategies_module, "get_strategy_rule", lambda slug: {"market_types": ["spot", "futures"], "allow_short": True})
    monkeypatch.setitem(strategies_module.STRATEGY_MAP, "test_strategy", strategy_fn)
    monkeypatch.setattr("app.services.connectors.get_client", lambda connector: client)
    monkeypatch.setattr("app.services.alerts.send_admin_user_alert_sync", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.alerts.format_user_failure_message", lambda **kwargs: "failure")
    monkeypatch.setattr("app.services.alerts.format_user_execution_message", lambda **kwargs: "execution")


def test_run_strategy_uses_last_closed_candle_and_closes_short_before_reentry(monkeypatch):
    db = _make_db()
    user, connector = _base_setup(db, market_type="futures")
    executed_orders = []

    existing = OpenPosition(
        user_id=user.id,
        connector_id=connector.id,
        platform=connector.platform,
        market_type="futures",
        symbol="BTC/USDT",
        position_side="short",
        entry_price=105.0,
        current_qty=3.0,
        is_open=True,
        meta_json={"stop_loss_price": 110.0},
    )
    db.add(existing)
    db.commit()

    frame = pd.DataFrame([
        {"timestamp": pd.Timestamp("2026-03-20T00:00:00"), "open": 99.0, "high": 101.0, "low": 98.0, "close": 100.0, "volume": 10.0},
        {"timestamp": pd.Timestamp("2026-03-20T00:15:00"), "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0, "volume": 11.0},
        {"timestamp": pd.Timestamp("2026-03-20T00:30:00"), "open": 101.0, "high": 103.0, "low": 100.0, "close": 102.0, "volume": 12.0},
    ])
    market_result = MarketFrameResult(
        frame=frame,
        meta={
            "source": "exchange_ohlcv",
            "exchange_price": 101.0,
            "health": {"has_unconfirmed_candle": True, "issues": ["last_candle_not_closed"]},
            "anomalies": {"severity": "ok", "issues": []},
        },
    )

    def _strategy_fn(data):
        assert float(data.iloc[-1]["close"]) == 101.0
        return "buy"

    client = _FakeClient(
        connector,
        position_context={"market_type": "futures", "has_position": True, "net_contracts": -3.0, "side": "short", "spot_base_free": 0.0, "spot_base_total": 0.0},
        executed_orders=executed_orders,
    )
    _patch_common(monkeypatch, client=client, market_result=market_result, strategy_fn=_strategy_fn, approved_qty=0.5)

    trading.run_strategy(
        db=db,
        user_id=user.id,
        connector_ids=[connector.id],
        symbols=["BTC/USDT"],
        timeframe="15m",
        strategy_slug="test_strategy",
        risk_per_trade=0.01,
        min_ml_probability=0.55,
        use_live_if_available=True,
        market_type="futures",
    )

    execute_call = next(item for item in executed_orders if item["stage"] == "execute")
    assert execute_call["reduce_only"] is True
    assert execute_call["quantity"] == 3.0

    db.refresh(existing)
    assert existing.is_open is False
    assert existing.current_qty == 0.0

    trade_run = db.query(TradeRun).order_by(TradeRun.id.desc()).first()
    notes = json.loads(trade_run.notes)
    assert notes["execution_environment"]["applied"] == ["time_sync", "margin_mode:isolated"]
    assert notes["execution_environment"]["futures_position_mode"] == "oneway"
    assert notes["execution_environment"]["retry_attempts"] == 4
    assert notes["order_preview"]["reduce_only"] is True
    assert notes["order_preview"]["reduce_only_reason"] == "close_short_before_reentry"
    assert notes["pretrade"]["ok"] is True
    assert notes["decision_summary"]["decision"] == "executed"


def test_run_strategy_opens_new_futures_long_with_execution_environment_snapshot(monkeypatch):
    db = _make_db()
    user, connector = _base_setup(db, market_type="futures")
    executed_orders = []

    frame = pd.DataFrame([
        {"timestamp": pd.Timestamp("2026-03-20T00:00:00"), "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 10.0},
        {"timestamp": pd.Timestamp("2026-03-20T00:15:00"), "open": 100.0, "high": 111.0, "low": 99.0, "close": 110.0, "volume": 11.0},
    ])
    market_result = MarketFrameResult(
        frame=frame,
        meta={
            "source": "exchange_ohlcv",
            "exchange_price": 110.0,
            "health": {"has_unconfirmed_candle": False, "issues": []},
            "anomalies": {"severity": "ok", "issues": []},
        },
    )

    client = _FakeClient(
        connector,
        position_context={"market_type": "futures", "has_position": False, "net_contracts": 0.0, "side": None, "spot_base_free": 0.0, "spot_base_total": 0.0},
        executed_orders=executed_orders,
    )
    _patch_common(monkeypatch, client=client, market_result=market_result, strategy_fn=lambda data: "buy", approved_qty=1.25)

    trading.run_strategy(
        db=db,
        user_id=user.id,
        connector_ids=[connector.id],
        symbols=["BTC/USDT"],
        timeframe="15m",
        strategy_slug="test_strategy",
        risk_per_trade=0.01,
        min_ml_probability=0.55,
        use_live_if_available=True,
        market_type="futures",
    )

    execute_call = next(item for item in executed_orders if item["stage"] == "execute")
    assert execute_call["reduce_only"] is False
    assert execute_call["quantity"] == 1.25

    position = db.query(OpenPosition).filter(OpenPosition.connector_id == connector.id, OpenPosition.is_open.is_(True)).one()
    assert position.position_side == "long"
    assert position.current_qty == 1.25

    trade_run = db.query(TradeRun).order_by(TradeRun.id.desc()).first()
    notes = json.loads(trade_run.notes)
    assert notes["execution_environment"]["recv_window_ms"] == 8000
    assert notes["execution_environment"]["request_timeout_ms"] == 12000
    assert notes["execution_environment"]["retry_attempts"] == 4
    assert notes["execution_environment"]["retry_delay_ms"] == 125
    assert notes["execution_environment"]["futures_margin_mode"] == "isolated"
    assert notes["execution_environment"]["futures_position_mode"] == "oneway"
    assert notes["order_preview"]["reduce_only"] is False
    assert notes["order_preview"]["reduce_only_reason"] is None
    assert notes["pretrade"]["normalized_quantity"] == 1.25
    assert notes["decision_summary"]["decision"] == "executed"


def test_run_strategy_closes_long_reduce_only_in_oneway_mode(monkeypatch):
    db = _make_db()
    user, connector = _base_setup(db, market_type="futures")
    executed_orders = []

    existing = OpenPosition(
        user_id=user.id,
        connector_id=connector.id,
        platform=connector.platform,
        market_type="futures",
        symbol="BTC/USDT",
        position_side="long",
        entry_price=100.0,
        current_qty=2.5,
        is_open=True,
        meta_json={"stop_loss_price": 95.0},
    )
    db.add(existing)
    db.commit()

    frame = pd.DataFrame([
        {"timestamp": pd.Timestamp("2026-03-20T00:00:00"), "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 10.0},
        {"timestamp": pd.Timestamp("2026-03-20T00:15:00"), "open": 100.0, "high": 102.0, "low": 97.0, "close": 98.0, "volume": 11.0},
    ])
    market_result = MarketFrameResult(
        frame=frame,
        meta={
            "source": "exchange_ohlcv",
            "exchange_price": 98.0,
            "health": {"has_unconfirmed_candle": False, "issues": []},
            "anomalies": {"severity": "ok", "issues": []},
        },
    )

    client = _FakeClient(
        connector,
        position_context={"market_type": "futures", "has_position": True, "net_contracts": 2.5, "side": "long", "spot_base_free": 0.0, "spot_base_total": 0.0},
        executed_orders=executed_orders,
    )
    _patch_common(monkeypatch, client=client, market_result=market_result, strategy_fn=lambda data: "sell", approved_qty=0.75)

    trading.run_strategy(
        db=db,
        user_id=user.id,
        connector_ids=[connector.id],
        symbols=["BTC/USDT"],
        timeframe="15m",
        strategy_slug="test_strategy",
        risk_per_trade=0.01,
        min_ml_probability=0.55,
        use_live_if_available=True,
        market_type="futures",
    )

    execute_call = next(item for item in executed_orders if item["stage"] == "execute")
    assert execute_call["reduce_only"] is True
    assert execute_call["quantity"] == 2.5

    db.refresh(existing)
    assert existing.is_open is False
    assert existing.current_qty == 0.0

    trade_run = db.query(TradeRun).order_by(TradeRun.id.desc()).first()
    notes = json.loads(trade_run.notes)
    assert notes["execution_environment"]["futures_position_mode"] == "oneway"
    assert notes["order_preview"]["reduce_only"] is True
    assert notes["order_preview"]["reduce_only_reason"] == "close_long_before_reentry"
    assert notes["pretrade"]["normalized_quantity"] == 2.5
    assert notes["decision_summary"]["decision"] == "executed"


def test_run_strategy_scales_into_existing_futures_long_without_reduce_only(monkeypatch):
    db = _make_db()
    user, connector = _base_setup(db, market_type="futures")
    executed_orders = []

    existing = OpenPosition(
        user_id=user.id,
        connector_id=connector.id,
        platform=connector.platform,
        market_type="futures",
        symbol="BTC/USDT",
        position_side="long",
        entry_price=100.0,
        current_qty=2.0,
        is_open=True,
        meta_json={"stop_loss_price": 95.0},
    )
    db.add(existing)
    db.commit()

    frame = pd.DataFrame([
        {"timestamp": pd.Timestamp("2026-03-20T00:00:00"), "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 10.0},
        {"timestamp": pd.Timestamp("2026-03-20T00:15:00"), "open": 100.0, "high": 111.0, "low": 99.0, "close": 110.0, "volume": 11.0},
    ])
    market_result = MarketFrameResult(
        frame=frame,
        meta={
            "source": "exchange_ohlcv",
            "exchange_price": 110.0,
            "health": {"has_unconfirmed_candle": False, "issues": []},
            "anomalies": {"severity": "ok", "issues": []},
        },
    )

    client = _FakeClient(
        connector,
        position_context={"market_type": "futures", "has_position": True, "net_contracts": 2.0, "side": "long", "spot_base_free": 0.0, "spot_base_total": 0.0},
        executed_orders=executed_orders,
    )
    _patch_common(monkeypatch, client=client, market_result=market_result, strategy_fn=lambda data: "buy", approved_qty=1.0)

    trading.run_strategy(
        db=db,
        user_id=user.id,
        connector_ids=[connector.id],
        symbols=["BTC/USDT"],
        timeframe="15m",
        strategy_slug="test_strategy",
        risk_per_trade=0.01,
        min_ml_probability=0.55,
        use_live_if_available=True,
        market_type="futures",
    )

    db.refresh(existing)
    assert existing.is_open is True
    assert existing.current_qty == 3.0
    assert round(existing.entry_price, 6) == round((100.0 * 2.0 + 110.0 * 1.0) / 3.0, 6)

    trade_run = db.query(TradeRun).order_by(TradeRun.id.desc()).first()
    notes = json.loads(trade_run.notes)
    assert notes["order_preview"]["reduce_only"] is False
    assert notes["order_preview"]["reduce_only_reason"] is None
    assert notes["pretrade"]["normalized_quantity"] == 1.0
    assert notes["decision_summary"]["decision"] == "executed"


def test_run_strategy_paper_mode_keeps_execution_environment_snapshot(monkeypatch):
    db = _make_db()
    user, connector = _base_setup(db, market_type="futures")
    connector.mode = "paper"
    connector.config_json["futures_position_mode"] = "hedge"
    connector.config_json["leverage_profile"] = "conservative"
    db.add(connector)
    db.commit()

    executed_orders = []
    frame = pd.DataFrame([
        {"timestamp": pd.Timestamp("2026-03-20T00:00:00"), "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 10.0},
        {"timestamp": pd.Timestamp("2026-03-20T00:15:00"), "open": 100.0, "high": 111.0, "low": 99.0, "close": 110.0, "volume": 11.0},
    ])
    market_result = MarketFrameResult(
        frame=frame,
        meta={
            "source": "exchange_ohlcv",
            "exchange_price": 110.0,
            "health": {"has_unconfirmed_candle": False, "issues": []},
            "anomalies": {"severity": "ok", "issues": []},
        },
    )

    client = _FakeClient(
        connector,
        position_context={"market_type": "futures", "has_position": False, "net_contracts": 0.0, "side": None, "spot_base_free": 0.0, "spot_base_total": 0.0},
        executed_orders=executed_orders,
    )
    _patch_common(monkeypatch, client=client, market_result=market_result, strategy_fn=lambda data: "buy", approved_qty=0.8)

    result = trading.run_strategy(
        db=db,
        user_id=user.id,
        connector_ids=[connector.id],
        symbols=["BTC/USDT"],
        timeframe="15m",
        strategy_slug="test_strategy",
        risk_per_trade=0.01,
        min_ml_probability=0.55,
        use_live_if_available=False,
        market_type="futures",
    )

    assert result[0]["status"] == "paper-filled"

    trade_run = db.query(TradeRun).order_by(TradeRun.id.desc()).first()
    notes = json.loads(trade_run.notes)
    assert notes["execution_environment"]["mode"] == "paper"
    assert notes["execution_environment"]["warnings"] == ["paper_mode_environment"]
    assert notes["execution_environment"]["futures_position_mode"] == "hedge"
    assert notes["execution_environment"]["leverage_profile"] == "none"
    assert notes["order_preview"]["reduce_only"] is False
    assert notes["pretrade"]["normalized_quantity"] == 0.8
    assert notes["decision_summary"]["decision"] == "executed"


def test_run_strategy_scales_into_existing_spot_position_instead_of_creating_duplicate(monkeypatch):
    db = _make_db()
    user, connector = _base_setup(db, market_type="spot")
    executed_orders = []

    existing = OpenPosition(
        user_id=user.id,
        connector_id=connector.id,
        platform=connector.platform,
        market_type="spot",
        symbol="BTC/USDT",
        position_side="long",
        entry_price=100.0,
        current_qty=2.0,
        is_open=True,
        meta_json={"stop_loss_price": 95.0},
    )
    db.add(existing)
    db.commit()

    frame = pd.DataFrame([
        {"timestamp": pd.Timestamp("2026-03-20T00:00:00"), "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 10.0},
        {"timestamp": pd.Timestamp("2026-03-20T00:15:00"), "open": 100.0, "high": 111.0, "low": 99.0, "close": 110.0, "volume": 11.0},
    ])
    market_result = MarketFrameResult(
        frame=frame,
        meta={
            "source": "exchange_ohlcv",
            "exchange_price": 110.0,
            "health": {"has_unconfirmed_candle": False, "issues": []},
            "anomalies": {"severity": "ok", "issues": []},
        },
    )

    client = _FakeClient(
        connector,
        position_context={"market_type": "spot", "has_position": True, "net_contracts": 0.0, "side": "long", "spot_base_free": 2.0, "spot_base_total": 2.0},
        executed_orders=executed_orders,
    )
    _patch_common(monkeypatch, client=client, market_result=market_result, strategy_fn=lambda data: "buy", approved_qty=1.0)

    trading.run_strategy(
        db=db,
        user_id=user.id,
        connector_ids=[connector.id],
        symbols=["BTC/USDT"],
        timeframe="15m",
        strategy_slug="test_strategy",
        risk_per_trade=0.01,
        min_ml_probability=0.55,
        use_live_if_available=True,
        market_type="spot",
    )

    positions = db.query(OpenPosition).filter(OpenPosition.connector_id == connector.id, OpenPosition.is_open.is_(True)).all()
    assert len(positions) == 1
    db.refresh(existing)
    assert existing.current_qty == 3.0
    assert round(existing.entry_price, 6) == round((100.0 * 2.0 + 110.0 * 1.0) / 3.0, 6)

    trade_run = db.query(TradeRun).order_by(TradeRun.id.desc()).first()
    notes = json.loads(trade_run.notes)
    assert notes["decision_summary"]["decision"] == "executed"
