from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import BotSession, Connector, User
from app.routers import api


def _session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'connector-persistence.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def _base_user_and_connector(db, *, market_type: str = "futures"):
    user = User(email="persist@test.dev", name="Persist", hashed_password="x", is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)

    connector = Connector(
        user_id=user.id,
        platform="binance",
        label="Primary",
        mode="live",
        market_type=market_type,
        is_enabled=True,
        symbols_json={"symbols": ["BTC/USDT"]},
        config_json={
            "market_type": market_type,
            "defaultType": "future" if market_type == "futures" else "spot",
            "futures_margin_mode": "isolated",
            "futures_position_mode": "hedge",
            "futures_leverage": 7,
            "retry_attempts": 3,
        },
        encrypted_secret_blob="{}",
    )
    db.add(connector)
    db.commit()
    db.refresh(connector)
    return user, connector


def test_update_connector_clears_futures_only_config_when_switching_to_spot(tmp_path, monkeypatch):
    Session = _session_factory(tmp_path)
    db = Session()
    monkeypatch.setattr(api, "_notify_user_info", lambda *args, **kwargs: None)
    try:
        user, connector = _base_user_and_connector(db, market_type="futures")

        payload = api.ConnectorUpdate(
            market_type="spot",
            config={
                "futures_margin_mode": None,
                "futures_position_mode": None,
                "futures_leverage": None,
                "retry_attempts": 1,
            },
        )

        api.update_connector(connector.id, payload=payload, db=db, user=user)
        db.refresh(connector)

        assert connector.market_type == "spot"
        assert connector.config_json["market_type"] == "spot"
        assert connector.config_json["defaultType"] == "spot"
        assert connector.config_json["retry_attempts"] == 1
        assert "futures_margin_mode" not in connector.config_json
        assert "futures_position_mode" not in connector.config_json
        assert "futures_leverage" not in connector.config_json
    finally:
        db.close()


def test_update_bot_session_rejects_fixed_amount_mode_without_amount(tmp_path):
    Session = _session_factory(tmp_path)
    db = Session()
    try:
        user, connector = _base_user_and_connector(db, market_type="futures")
        session = BotSession(
            user_id=user.id,
            connector_id=connector.id,
            market_type="futures",
            strategy_slug="ema_rsi_adx_stack",
            timeframe="15m",
            symbols_json={"symbols": ["BTC/USDT"]},
            interval_minutes=15,
            risk_per_trade=0.01,
            trade_amount_mode="inherit",
            min_ml_probability=0.55,
            take_profit_mode="percent",
            take_profit_value=1.5,
            stop_loss_mode="percent",
            stop_loss_value=1.0,
            trailing_stop_mode="percent",
            trailing_stop_value=0.8,
            is_active=True,
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        try:
            api.update_bot_session(
                session.id,
                payload=api.BotSessionUpdate(trade_amount_mode="fixed_usd"),
                db=db,
                user=user,
            )
        except api.HTTPException as exc:
            assert exc.status_code == 400
            assert "PRECHECK_CONFIG_NOT_PERSISTED" in str(exc.detail)
        else:
            raise AssertionError("Expected fixed_usd session update without amount_per_trade to fail")
    finally:
        db.close()


def test_update_bot_session_switches_modes_and_clears_opposite_amount_field(tmp_path, monkeypatch):
    Session = _session_factory(tmp_path)
    db = Session()
    monkeypatch.setattr(api, "_notify_user_info", lambda *args, **kwargs: None)
    monkeypatch.setattr(api, "_ensure_strategy_control", lambda db, user_id: type("Ctl", (), {"managed_by_admin": False, "allowed_strategies_json": {"items": api.ALL_STRATEGIES}})())
    try:
        user, connector = _base_user_and_connector(db, market_type="futures")
        session = BotSession(
            user_id=user.id,
            connector_id=connector.id,
            market_type="futures",
            strategy_slug="ema_rsi_adx_stack",
            timeframe="15m",
            symbols_json={"symbols": ["BTC/USDT"]},
            interval_minutes=15,
            risk_per_trade=0.01,
            trade_amount_mode="fixed_usd",
            amount_per_trade=75.0,
            amount_percentage=None,
            min_ml_probability=0.55,
            take_profit_mode="percent",
            take_profit_value=1.5,
            stop_loss_mode="percent",
            stop_loss_value=1.0,
            trailing_stop_mode="percent",
            trailing_stop_value=0.8,
            is_active=True,
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        api.update_bot_session(
            session.id,
            payload=api.BotSessionUpdate(trade_amount_mode="balance_percent", amount_percentage=12.5),
            db=db,
            user=user,
        )
        db.refresh(session)

        assert session.trade_amount_mode == "balance_percent"
        assert session.amount_percentage == 12.5
        assert session.amount_per_trade is None
    finally:
        db.close()


def test_update_bot_session_persists_live_name_and_dynamic_scan_settings(tmp_path, monkeypatch):
    Session = _session_factory(tmp_path)
    db = Session()
    monkeypatch.setattr(api, "_notify_user_info", lambda *args, **kwargs: None)
    monkeypatch.setattr(api, "_ensure_strategy_control", lambda db, user_id: type("Ctl", (), {"managed_by_admin": False, "allowed_strategies_json": {"items": api.ALL_STRATEGIES}})())
    try:
        user, connector = _base_user_and_connector(db, market_type="futures")
        session = BotSession(
            user_id=user.id,
            connector_id=connector.id,
            session_name="Base",
            market_type="futures",
            strategy_slug="ema_rsi_adx_stack",
            timeframe="15m",
            symbols_json={"symbols": ["BTC/USDT"], "symbol_source_mode": "manual", "dynamic_symbol_limit": 5},
            interval_minutes=15,
            risk_per_trade=0.01,
            trade_amount_mode="fixed_usd",
            amount_per_trade=75.0,
            min_ml_probability=0.55,
            use_live_if_available=False,
            take_profit_mode="percent",
            take_profit_value=1.5,
            stop_loss_mode="percent",
            stop_loss_value=1.0,
            trailing_stop_mode="percent",
            trailing_stop_value=0.8,
            is_active=True,
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        api.update_bot_session(
            session.id,
            payload=api.BotSessionUpdate(
                session_name="Quantum Momentum",
                symbol_source_mode="dynamic",
                dynamic_symbol_limit=12,
                use_live_if_available=True,
                amount_per_trade=90.0,
            ),
            db=db,
            user=user,
        )
        db.refresh(session)

        assert session.session_name == "Quantum Momentum"
        assert session.use_live_if_available is True
        assert session.amount_per_trade == 90.0
        assert session.symbols_json["symbol_source_mode"] == "dynamic"
        assert session.symbols_json["dynamic_symbol_limit"] == 12
    finally:
        db.close()


def test_create_connector_forces_live_mode_and_repairs_zero_sizing_defaults(tmp_path, monkeypatch):
    Session = _session_factory(tmp_path)
    db = Session()
    monkeypatch.setattr(api, "_notify_user_info", lambda *args, **kwargs: None)
    try:
        user = User(email="live@test.dev", name="Live", hashed_password="x", is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)

        payload = api.ConnectorCreate(
            platform="bybit",
            label="Bybit principal",
            mode="paper",
            market_type="spot",
            symbols=["ETH/USDT"],
            config={
                "trade_amount_mode": "fixed_usd",
                "fixed_trade_amount_usd": 0,
                "trade_balance_percent": 7.5,
            },
            secrets={},
        )

        result = api.create_connector(payload=payload, db=db, user=user)
        connector = db.query(Connector).filter(Connector.id == result["connector_id"]).first()

        assert connector.mode == "live"
        assert connector.config_json["trade_amount_mode"] == "fixed_usd"
        assert connector.config_json["fixed_trade_amount_usd"] >= 5
        assert connector.config_json["trade_balance_percent"] == 7.5
        assert connector.config_json["sandbox"] is False
    finally:
        db.close()


def test_list_bot_sessions_repairs_legacy_zero_fixed_amount_and_forces_live_execution(tmp_path, monkeypatch):
    Session = _session_factory(tmp_path)
    db = Session()
    monkeypatch.setattr(api, "_alert_admin_failure", lambda *args, **kwargs: None)
    try:
        user, connector = _base_user_and_connector(db, market_type="spot")
        connector.mode = "paper"
        connector.symbols_json = {"symbols": ["BTC/USDT"]}
        connector.config_json = {
            "market_type": "spot",
            "trade_amount_mode": "fixed_usd",
            "fixed_trade_amount_usd": 0,
            "trade_balance_percent": 0,
        }
        session = BotSession(
            user_id=user.id,
            connector_id=connector.id,
            session_name="Momentum BTC",
            market_type="spot",
            strategy_slug="ema_rsi_adx_stack",
            timeframe="15m",
            symbols_json={"symbols": ["BTC/USDT"]},
            interval_minutes=15,
            risk_per_trade=0.01,
            trade_amount_mode="fixed_usd",
            amount_per_trade=None,
            amount_percentage=None,
            min_ml_probability=0.55,
            use_live_if_available=False,
            take_profit_mode="percent",
            take_profit_value=1.5,
            stop_loss_mode="percent",
            stop_loss_value=1.0,
            trailing_stop_mode="percent",
            trailing_stop_value=0.8,
            is_active=True,
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        rows = api.list_bot_sessions(db=db, user=user)
        db.refresh(connector)
        db.refresh(session)

        assert rows[0]["session_name"] == "Momentum BTC"
        assert rows[0]["capital_per_operation"] >= 10
        assert connector.mode == "live"
        assert session.use_live_if_available is True
        assert session.amount_per_trade >= 10
    finally:
        db.close()
