from app.services.indicators import add_indicators


def ema_rsi(df):
    data = add_indicators(df)
    row = data.iloc[-1]
    if row["ema_fast"] > row["ema_slow"] and row["rsi"] < 68:
        return "buy"
    if row["ema_fast"] < row["ema_slow"] and row["rsi"] > 32:
        return "sell"
    return "hold"


def mean_reversion_zscore(df):
    data = add_indicators(df)
    row = data.iloc[-1]
    if row["zscore"] < -1.8:
        return "buy"
    if row["zscore"] > 1.8:
        return "sell"
    return "hold"


def momentum_breakout(df):
    data = add_indicators(df)
    row = data.iloc[-1]
    if row["close"] >= row["hh_20"] * 0.997:
        return "buy"
    if row["close"] <= row["ll_20"] * 1.003:
        return "sell"
    return "hold"


STRATEGY_MAP = {
    "ema_rsi": ema_rsi,
    "mean_reversion_zscore": mean_reversion_zscore,
    "momentum_breakout": momentum_breakout,
}
