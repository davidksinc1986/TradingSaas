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
    return out.dropna().reset_index(drop=True)
