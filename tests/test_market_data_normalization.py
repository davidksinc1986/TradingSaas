from __future__ import annotations

import pandas as pd

from app.services.market import _normalize_frame_price_scale


def test_normalize_frame_price_scale_rebases_outlier_close_to_exchange_price():
    frame = pd.DataFrame([
        {"timestamp": "2026-03-20T00:00:00", "open": 18000.0, "high": 18200.0, "low": 17950.0, "close": 18150.0, "volume": 1000},
        {"timestamp": "2026-03-20T00:15:00", "open": 18100.0, "high": 18300.0, "low": 18080.0, "close": 18156.0, "volume": 1200},
    ])

    normalized, meta = _normalize_frame_price_scale(frame, 92.0)

    assert meta["applied"] is True
    assert round(float(normalized.iloc[-1]["close"]), 4) == 92.0
    assert meta["difference_pct_after"] == 0.0
