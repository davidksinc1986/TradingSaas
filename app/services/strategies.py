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


def macd_trend_pullback(df):
    data = add_indicators(df)
    row = data.iloc[-1]
    if row["ema_fast"] > row["ema_slow"] and row["macd"] > row["macd_signal"] and row["rsi"] < 62:
        return "buy"
    if row["ema_fast"] < row["ema_slow"] and row["macd"] < row["macd_signal"] and row["rsi"] > 38:
        return "sell"
    return "hold"


def bollinger_rsi_reversal(df):
    data = add_indicators(df)
    row = data.iloc[-1]
    if row["close"] <= row["bb_low"] and row["rsi"] < 35:
        return "buy"
    if row["close"] >= row["bb_high"] and row["rsi"] > 65:
        return "sell"
    return "hold"


def adx_trend_follow(df):
    data = add_indicators(df)
    row = data.iloc[-1]
    if row["adx"] >= 22 and row["ema_fast"] > row["ema_slow"]:
        return "buy"
    if row["adx"] >= 22 and row["ema_fast"] < row["ema_slow"]:
        return "sell"
    return "hold"


def stochastic_rebound(df):
    data = add_indicators(df)
    row = data.iloc[-1]
    if row["stoch_k"] < 20 and row["stoch_d"] < 25 and row["close"] > row["ema_fast"]:
        return "buy"
    if row["stoch_k"] > 80 and row["stoch_d"] > 75 and row["close"] < row["ema_fast"]:
        return "sell"
    return "hold"


STRATEGY_MAP = {
    "ema_rsi": ema_rsi,
    "mean_reversion_zscore": mean_reversion_zscore,
    "momentum_breakout": momentum_breakout,
    "macd_trend_pullback": macd_trend_pullback,
    "bollinger_rsi_reversal": bollinger_rsi_reversal,
    "adx_trend_follow": adx_trend_follow,
    "stochastic_rebound": stochastic_rebound,
}
