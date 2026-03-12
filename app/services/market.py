from datetime import datetime, timedelta
from random import gauss, random

import pandas as pd


def synthetic_ohlcv(symbol: str, periods: int = 300, timeframe: str = "1h") -> pd.DataFrame:
    seed_bias = (sum(ord(c) for c in symbol) % 17) / 1000
    drift = 0.0005 + seed_bias
    vol = 0.015 + ((sum(ord(c) for c in symbol) % 7) / 1000)
    end = datetime.utcnow()
    step = timedelta(hours=1 if timeframe.endswith("h") else 1)
    timestamps = [end - step * i for i in range(periods)][::-1]
    prices = [100.0 + (sum(ord(c) for c in symbol) % 50)]
    for _ in range(1, periods):
        shock = gauss(drift, vol)
        prices.append(max(1.0, prices[-1] * (1 + shock)))
    rows = []
    for ts, close in zip(timestamps, prices):
        high = close * (1 + abs(random()) * 0.01)
        low = close * (1 - abs(random()) * 0.01)
        open_ = close * (1 + gauss(0, 0.003))
        volume = abs(gauss(1000, 250))
        rows.append({"timestamp": ts, "open": open_, "high": high, "low": low, "close": close, "volume": volume})
    return pd.DataFrame(rows)
