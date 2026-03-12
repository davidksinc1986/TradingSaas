from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field


PLATFORMS = Literal["mt5", "ctrader", "tradingview", "binance", "bybit", "okx"]


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=6, max_length=255)


class UserLogin(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str


class ConnectorCreate(BaseModel):
    user_id: int | None = None
    platform: PLATFORMS
    label: str
    mode: Literal["paper", "live", "signal"] = "paper"
    market_type: Literal["spot", "futures", "cfd", "forex", "signals"] = "spot"
    symbols: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, Any] = Field(default_factory=dict)


class ConnectorUpdate(BaseModel):
    label: str | None = None
    mode: Literal["paper", "live", "signal"] | None = None
    market_type: Literal["spot", "futures", "cfd", "forex", "signals"] | None = None
    symbols: list[str] | None = None
    config: dict[str, Any] | None = None
    secrets: dict[str, Any] | None = None
    is_enabled: bool | None = None


class StrategyRequest(BaseModel):
    connector_ids: list[int]
    symbols: list[str]
    timeframe: str = "1h"
    strategy_slug: Literal["ema_rsi", "mean_reversion_zscore", "momentum_breakout"] = "ema_rsi"
    risk_per_trade: float = Field(default=0.01, gt=0, le=0.1)
    min_ml_probability: float = Field(default=0.55, ge=0, le=1)
    use_live_if_available: bool = False


class TradingViewWebhook(BaseModel):
    connector_id: int
    symbol: str
    side: Literal["buy", "sell"]
    price: float
    quantity: float = 0.0
    strategy_slug: str = "tradingview_alert"
    passphrase: str | None = None
    target_connector_id: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class AdminUserUpdate(BaseModel):
    is_active: bool | None = None
    is_admin: bool | None = None


class AdminUserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=6, max_length=255)


class AdminGrantUpdate(BaseModel):
    user_id: int
    platform: PLATFORMS
    is_enabled: bool = True
    max_symbols: int = 5
    max_daily_movements: int = 20
    notes: str | None = None


class AdminPolicyUpdate(BaseModel):
    platform: PLATFORMS
    is_enabled_global: bool | None = None
    allow_manual_symbols: bool | None = None
    top_symbols: list[str] | None = None
    allowed_symbols: list[str] | None = None
