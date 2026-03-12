def position_size(balance: float, risk_per_trade: float, price: float, stop_pct: float = 0.01) -> float:
    capital_at_risk = max(1.0, balance * risk_per_trade)
    risk_per_unit = max(price * stop_pct, 0.0001)
    qty = capital_at_risk / risk_per_unit
    return round(qty, 6)
