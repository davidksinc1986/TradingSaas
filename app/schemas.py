from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field

PLATFORMS = Literal["mt5", "ctrader", "tradingview", "binance", "bybit", "okx"]
STRATEGY_LITERAL = str


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
    strategy_slug: STRATEGY_LITERAL = "ema_rsi"
    risk_per_trade: float = Field(default=1, gt=0, le=100)
    min_ml_probability: float = Field(default=55, ge=0, le=100)
    use_live_if_available: bool = False
    take_profit_mode: Literal["percent", "usdt"] = "percent"
    take_profit_value: float = Field(default=1.5, gt=0)
    stop_loss_mode: Literal["percent", "usdt"] = "percent"
    stop_loss_value: float = Field(default=1.0, gt=0)
    trailing_stop_mode: Literal["percent", "usdt"] = "percent"
    trailing_stop_value: float = Field(default=0.8, gt=0)
    indicator_exit_enabled: bool = False
    indicator_exit_rule: Literal["macd_cross", "rsi_reversal", "ema_cross"] = "macd_cross"


class BotSessionCreate(BaseModel):
    connector_id: int
    symbols: list[str]
    timeframe: str = "5m"
    strategy_slug: STRATEGY_LITERAL = "ema_rsi"
    risk_per_trade: float = Field(default=1, gt=0, le=100)
    min_ml_probability: float = Field(default=55, ge=0, le=100)
    use_live_if_available: bool = False
    interval_minutes: int = Field(default=5, ge=1, le=1440)
    take_profit_mode: Literal["percent", "usdt"] = "percent"
    take_profit_value: float = Field(default=1.5, gt=0)
    stop_loss_mode: Literal["percent", "usdt"] = "percent"
    stop_loss_value: float = Field(default=1.0, gt=0)
    trailing_stop_mode: Literal["percent", "usdt"] = "percent"
    trailing_stop_value: float = Field(default=0.8, gt=0)
    indicator_exit_enabled: bool = False
    indicator_exit_rule: Literal["macd_cross", "rsi_reversal", "ema_cross"] = "macd_cross"


class BotSessionUpdate(BaseModel):
    is_active: bool | None = None
    interval_minutes: int | None = Field(default=None, ge=1, le=1440)
    symbols: list[str] | None = None
    timeframe: str | None = None
    strategy_slug: STRATEGY_LITERAL | None = None
    take_profit_mode: Literal["percent", "usdt"] | None = None
    take_profit_value: float | None = Field(default=None, gt=0)
    stop_loss_mode: Literal["percent", "usdt"] | None = None
    stop_loss_value: float | None = Field(default=None, gt=0)
    trailing_stop_mode: Literal["percent", "usdt"] | None = None
    trailing_stop_value: float | None = Field(default=None, gt=0)
    indicator_exit_enabled: bool | None = None
    indicator_exit_rule: Literal["macd_cross", "rsi_reversal", "ema_cross"] | None = None
    risk_per_trade: float | None = Field(default=None, gt=0, le=100)
    min_ml_probability: float | None = Field(default=None, ge=0, le=100)
    use_live_if_available: bool | None = None

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


class AdminStrategyControlUpdate(BaseModel):
    managed_by_admin: bool
    allowed_strategies: list[STRATEGY_LITERAL] = Field(default_factory=list)


class StrategyControlUpdate(BaseModel):
    allowed_strategies: list[STRATEGY_LITERAL] = Field(default_factory=list)


class AdminPricingConfigUpdate(BaseModel):
    base_commission_usd: float = Field(ge=0)
    cost_per_app_usd: float = Field(ge=0)
    cost_per_symbol_usd: float = Field(ge=0)
    cost_per_movement_usd: float = Field(ge=0)
    cost_per_gb_ram_usd: float = Field(ge=0)
    cost_per_gb_disk_usd: float = Field(ge=0)
    suggested_ram_per_app_gb: float = Field(gt=0)
    suggested_disk_per_app_gb: float = Field(gt=0)


class AdminPlanConfigPayload(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = ""
    apps: int = Field(ge=0)
    symbols: int = Field(ge=0)
    daily_movements: int = Field(ge=0)
    monthly_price_usd: float = Field(ge=0)
    is_custom: bool = False
    is_active: bool = True
    sort_order: int = 0
