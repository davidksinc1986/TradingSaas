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


def supertrend_volatility(df):
    data = add_indicators(df)
    row = data.iloc[-1]
    if row["adx"] > 25 and row["ret_1"] > 0 and row["close"] > row["ema_fast"]:
        return "buy"
    if row["adx"] > 25 and row["ret_1"] < 0 and row["close"] < row["ema_fast"]:
        return "sell"
    return "hold"


def kalman_trend_filter(df):
    data = add_indicators(df)
    row = data.iloc[-1]
    if row["ema_fast"] > row["mean_20"] and row["macd"] > 0 and row["rsi"] < 70:
        return "buy"
    if row["ema_fast"] < row["mean_20"] and row["macd"] < 0 and row["rsi"] > 30:
        return "sell"
    return "hold"


def atr_channel_breakout(df):
    data = add_indicators(df)
    row = data.iloc[-1]
    if row["close"] > row["bb_high"] and row["adx"] > 20:
        return "buy"
    if row["close"] < row["bb_low"] and row["adx"] > 20:
        return "sell"
    return "hold"


def volatility_parity_rebalance(df):
    data = add_indicators(df)
    row = data.iloc[-1]
    if row["vol_10"] < 0.018 and row["ema_fast"] > row["ema_slow"]:
        return "buy"
    if row["vol_10"] > 0.03 and row["ema_fast"] < row["ema_slow"]:
        return "sell"
    return "hold"


def pairs_spread_proxy(df):
    data = add_indicators(df)
    row = data.iloc[-1]
    if row["zscore"] < -2.2 and row["stoch_k"] < 25:
        return "buy"
    if row["zscore"] > 2.2 and row["stoch_k"] > 75:
        return "sell"
    return "hold"


def volatility_breakout(df):
    data = add_indicators(df)
    if len(data) < 2:
        return "hold"
    prev = data.iloc[-2]
    row = data.iloc[-1]
    k = 0.5
    breakout = row["open"] + k * (prev["high"] - prev["low"])
    if row["close"] > breakout and row["atr"] > row["atr_mean_20"]:
        return "buy"
    if row["close"] < row["open"] - k * (prev["high"] - prev["low"]) and row["atr"] > row["atr_mean_20"]:
        return "sell"
    return "hold"


def ema_rsi_adx_stack(df):
    data = add_indicators(df)
    row = data.iloc[-1]
    if row["ema_fast"] > row["ema_slow"] and row["rsi"] > 55 and row["adx"] > 20:
        return "buy"
    if row["ema_fast"] < row["ema_slow"] and row["rsi"] < 45 and row["adx"] > 20:
        return "sell"
    return "hold"


def volatility_compression_breakout(df):
    data = add_indicators(df)
    row = data.iloc[-1]
    squeeze = row["bb_high"] < row["kc_high"] and row["bb_low"] > row["kc_low"] and row["atr_contraction"] < 0.9
    if squeeze and row["close"] > row["hh_20"] * 0.998:
        return "buy"
    if squeeze and row["close"] < row["ll_20"] * 1.002:
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
    "supertrend_volatility": supertrend_volatility,
    "kalman_trend_filter": kalman_trend_filter,
    "atr_channel_breakout": atr_channel_breakout,
    "volatility_parity_rebalance": volatility_parity_rebalance,
    "pairs_spread_proxy": pairs_spread_proxy,
    "volatility_breakout": volatility_breakout,
    "ema_rsi_adx_stack": ema_rsi_adx_stack,
    "volatility_compression_breakout": volatility_compression_breakout,
}

SPOT_TOP_STRATEGIES = [
    "ema_rsi",
    "mean_reversion_zscore",
    "bollinger_rsi_reversal",
    "stochastic_rebound",
    "volatility_parity_rebalance",
    "pairs_spread_proxy",
    "ema_rsi_adx_stack",
    "volatility_compression_breakout",
]

FUTURES_TOP_STRATEGIES = [
    "momentum_breakout",
    "macd_trend_pullback",
    "adx_trend_follow",
    "supertrend_volatility",
    "kalman_trend_filter",
    "atr_channel_breakout",
    "volatility_breakout",
    "volatility_compression_breakout",
]

ALL_STRATEGIES = list(STRATEGY_MAP.keys())
