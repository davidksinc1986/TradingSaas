import numpy as np
import pandas as pd


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["ema_fast"] = out["close"].ewm(span=12).mean()
    out["ema_slow"] = out["close"].ewm(span=26).mean()

    delta = out["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    out["rsi"] = 100 - (100 / (1 + rs))

    out["ret_1"] = out["close"].pct_change(1)
    out["ret_5"] = out["close"].pct_change(5)
    out["vol_10"] = out["close"].pct_change().rolling(10).std()
    out["mean_20"] = out["close"].rolling(20).mean()
    out["std_20"] = out["close"].rolling(20).std()
    out["zscore"] = (out["close"] - out["mean_20"]) / out["std_20"].replace(0, np.nan)
    out["hh_20"] = out["high"].rolling(20).max()
    out["ll_20"] = out["low"].rolling(20).min()

    out["bb_high"] = out["mean_20"] + 2 * out["std_20"]
    out["bb_low"] = out["mean_20"] - 2 * out["std_20"]

    ema12 = out["close"].ewm(span=12).mean()
    ema26 = out["close"].ewm(span=26).mean()
    out["macd"] = ema12 - ema26
    out["macd_signal"] = out["macd"].ewm(span=9).mean()

    low14 = out["low"].rolling(14).min()
    high14 = out["high"].rolling(14).max()
    out["stoch_k"] = 100 * (out["close"] - low14) / (high14 - low14).replace(0, np.nan)
    out["stoch_d"] = out["stoch_k"].rolling(3).mean()

    tr = pd.concat([
        out["high"] - out["low"],
        (out["high"] - out["close"].shift()).abs(),
        (out["low"] - out["close"].shift()).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    out["atr"] = atr
    out["atr_mean_20"] = atr.rolling(20).mean()
    plus_dm = (out["high"].diff()).clip(lower=0)
    minus_dm = (-out["low"].diff()).clip(lower=0)
    plus_di = 100 * (plus_dm.rolling(14).mean() / atr.replace(0, np.nan))
    minus_di = 100 * (minus_dm.rolling(14).mean() / atr.replace(0, np.nan))
    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)) * 100
    out["adx"] = dx.rolling(14).mean()

    out["kc_mid"] = out["mean_20"]
    out["kc_high"] = out["kc_mid"] + 1.5 * out["atr"]
    out["kc_low"] = out["kc_mid"] - 1.5 * out["atr"]
    out["bb_width"] = (out["bb_high"] - out["bb_low"]) / out["mean_20"].replace(0, np.nan)
    out["atr_contraction"] = out["atr"] / out["atr_mean_20"].replace(0, np.nan)

    return out.dropna().reset_index(drop=True)
