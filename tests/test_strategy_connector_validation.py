from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Connector, User
from app.routers.api import _validate_strategy_connectors
from app.services.strategies import get_strategy_rule


def _session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'strategy-validation.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def test_validate_strategy_connectors_rejects_futures_incompatible_strategy(tmp_path):
    Session = _session_factory(tmp_path)
    db = Session()
    try:
        user = User(email="futures@example.com", name="Futures User", hashed_password="x")
        db.add(user)
        db.commit()
        db.refresh(user)
        connector = Connector(user_id=user.id, platform="binance", label="Binance Futures", market_type="futures", mode="paper")
        db.add(connector)
        db.commit()
        db.refresh(connector)

        try:
            _validate_strategy_connectors(db, user_id=user.id, connector_ids=[connector.id], strategy_slug="ema_rsi")
        except HTTPException as exc:
            assert exc.status_code == 400
            assert "ema_rsi" in str(exc.detail)
            assert "Binance Futures" in str(exc.detail)
            assert "futures" in str(exc.detail)
        else:
            raise AssertionError("Expected a HTTPException for incompatible futures strategy")
    finally:
        db.close()


def test_validate_strategy_connectors_accepts_shared_spot_and_futures_strategy(tmp_path):
    Session = _session_factory(tmp_path)
    db = Session()
    try:
        user = User(email="stack@example.com", name="Stack User", hashed_password="x")
        db.add(user)
        db.commit()
        db.refresh(user)
        connector = Connector(user_id=user.id, platform="bybit", label="Bybit Futures", market_type="futures", mode="paper")
        db.add(connector)
        db.commit()
        db.refresh(connector)

        validated = _validate_strategy_connectors(db, user_id=user.id, connector_ids=[connector.id], strategy_slug="ema_rsi_adx_stack")

        assert [item.id for item in validated] == [connector.id]
        assert "futures" in get_strategy_rule("ema_rsi_adx_stack")["market_types"]
    finally:
        db.close()
