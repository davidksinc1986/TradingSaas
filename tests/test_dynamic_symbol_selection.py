from types import SimpleNamespace

from app.services.scanner import select_symbols_for_run
from app.services.trading import _resolve_order_price_context


def test_select_symbols_for_run_forces_dynamic_limit(monkeypatch):
    scored = {
        "AAA/USDT": {"symbol": "AAA/USDT", "score": 10},
        "BBB/USDT": {"symbol": "BBB/USDT", "score": 20},
        "CCC/USDT": {"symbol": "CCC/USDT", "score": 30},
    }

    monkeypatch.setattr("app.services.scanner._score_symbol", lambda symbol, timeframe, connector=None: scored[symbol])

    selected, meta = select_symbols_for_run(
        connector_id=1,
        timeframe="15m",
        fallback_symbols=["AAA/USDT", "BBB/USDT", "CCC/USDT"],
        cfg={"auto_scan_enabled": False},
        connector=None,
        force_dynamic=True,
        max_symbols_override=2,
    )

    assert selected == ["CCC/USDT", "BBB/USDT"]
    assert meta["mode"] == "auto"
    assert meta["max_symbols"] == 2


def test_resolve_order_price_context_prefers_execution_reference():
    client = SimpleNamespace(
        resolve_execution_reference_price=lambda symbol, order_type, side, analysis_price: {
            "value": 0.5897,
            "source": "ticker_last",
        }
    )

    result = _resolve_order_price_context(
        client=client,
        symbol="XRP/USDT",
        signal="buy",
        analysis_price=589.7264,
        market_meta={"exchange_price": 0.5895},
    )

    assert result["resolved_price"] == 0.5897
    assert result["resolved_source"] == "ticker_last"
