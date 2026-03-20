import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import OpenPosition, TradeLog, TradeRun, User
from app.services.market import detect_market_anomalies
from app.services.risk_engine import RiskGuardrails, build_trade_risk_plan, summarize_portfolio_risk


def _make_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def test_build_trade_risk_plan_caps_qty_and_blocks_critical_anomalies():
    guardrails = RiskGuardrails(max_risk_per_trade=0.02, max_portfolio_heat=0.05, max_symbol_concentration=0.3, max_open_positions=3)

    capped = build_trade_risk_plan(
        available_balance=1000,
        price=100,
        stop_loss_price=95,
        requested_qty=10,
        risk_per_trade=0.03,
        current_open_notional=200,
        current_open_risk=10,
        current_symbol_notional=50,
        current_open_positions=1,
        guardrails=guardrails,
        market_meta={"source": "exchange_ohlcv", "health": {"issues": []}, "anomalies": {"severity": "ok", "issues": []}},
    )

    assert capped.approved is True
    assert capped.approved_qty == 4.8
    assert "qty_capped_by_risk_engine" in capped.warnings

    blocked = build_trade_risk_plan(
        available_balance=1000,
        price=100,
        stop_loss_price=95,
        requested_qty=1,
        risk_per_trade=0.01,
        current_open_notional=0,
        current_open_risk=0,
        current_symbol_notional=0,
        current_open_positions=0,
        guardrails=guardrails,
        market_meta={"source": "synthetic_fallback", "health": {"issues": ["stale_feed"]}, "anomalies": {"severity": "critical", "issues": ["non_positive_prices"]}},
    )

    assert blocked.approved is False
    assert "market_data_anomaly" in blocked.block_reasons
    assert "synthetic_market_data" in blocked.warnings


def test_detect_market_anomalies_flags_broken_ohlcv_rows():
    frame = pd.DataFrame([
        {"timestamp": "2026-03-19T00:00:00", "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 10},
        {"timestamp": "2026-03-19T01:00:00", "open": 101, "high": 90, "low": 102, "close": -5, "volume": 0},
    ])

    result = detect_market_anomalies(frame)

    assert result["severity"] == "critical"
    assert "ohlc_consistency_broken" in result["issues"]
    assert "non_positive_prices" in result["issues"]


def test_summarize_portfolio_risk_reports_drawdown_and_kill_switch_signal():
    db = _make_db()
    user = User(email="risk@test.dev", name="Risk User", hashed_password="x", is_active=True, is_admin=False)
    db.add(user)
    db.commit()
    db.refresh(user)

    db.add(OpenPosition(
        user_id=user.id,
        connector_id=1,
        platform="binance",
        market_type="spot",
        symbol="BTC/USDT",
        position_side="long",
        entry_price=100,
        current_qty=2,
        is_open=True,
        meta_json={"stop_loss_price": 90},
    ))
    db.add_all([
        TradeLog(user_id=user.id, connector_id=1, platform="binance", symbol="BTC/USDT", side="buy", quantity=1, price=100, status="filled", pnl=50),
        TradeLog(user_id=user.id, connector_id=1, platform="binance", symbol="ETH/USDT", side="sell", quantity=1, price=100, status="filled", pnl=-80),
    ])
    db.add(TradeRun(
        user_id=user.id,
        connector_id=1,
        strategy_slug="ema_rsi",
        symbol="BTC/USDT",
        timeframe="1h",
        signal="buy",
        ml_probability=0.6,
        quantity=1,
        status="skipped",
        notes='{"market_data":{"source":"synthetic_fallback","health":{"issues":["stale_feed"]}}}',
    ))
    db.commit()

    summary = summarize_portfolio_risk(db, user.id)

    assert summary["open_positions"] == 1
    assert summary["estimated_open_risk"] == 20.0
    assert summary["kill_switch_armed"] is True
    assert any(alert in summary["alerts"] for alert in {"drawdown_limit_breached", "market_data_quality_degraded"})
