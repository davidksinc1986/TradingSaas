from sklearn.linear_model import LogisticRegression

from app.services.indicators import add_indicators

FEATURES = ["ema_fast", "ema_slow", "rsi", "ret_1", "ret_5", "vol_10", "zscore"]


def train_and_score(df):
    data = add_indicators(df)
    if len(data) < 60:
        return 0.5
    data["target"] = (data["close"].shift(-1) > data["close"]).astype(int)
    data = data.dropna()
    train = data.iloc[:-1]
    latest = data.iloc[[-1]]
    if train["target"].nunique() < 2:
        return 0.5
    model = LogisticRegression(max_iter=500)
    model.fit(train[FEATURES], train["target"])
    prob = model.predict_proba(latest[FEATURES])[0][1]
    return float(prob)
