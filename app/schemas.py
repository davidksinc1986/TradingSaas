from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, model_validator

PLATFORMS = Literal["mt5", "ctrader", "tradingview", "binance", "bybit", "okx"]
STRATEGY_LITERAL = str
MARKET_TYPES = Literal["spot", "futures", "cfd", "forex", "signals"]


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
    mode: Literal["paper", "live", "signal"] = "live"
    market_type: MARKET_TYPES = "spot"
    symbols: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    secrets: dict[str, Any] = Field(default_factory=dict)


class ConnectorUpdate(BaseModel):
    label: str | None = None
    mode: Literal["paper", "live", "signal"] | None = None
    market_type: MARKET_TYPES | None = None
    symbols: list[str] | None = None
    config: dict[str, Any] | None = None
    secrets: dict[str, Any] | None = None
    is_enabled: bool | None = None


class StrategyRiskMixin(BaseModel):
    @model_validator(mode="after")
    def validate_tp_sl_rules(self):
        tp_mode = getattr(self, "take_profit_mode", "percent")
        sl_mode = getattr(self, "stop_loss_mode", "percent")
        tp_value = float(getattr(self, "take_profit_value", 0) or 0)
        sl_value = float(getattr(self, "stop_loss_value", 0) or 0)
        trailing_value = float(getattr(self, "trailing_stop_value", 0) or 0)

        if sl_value <= 0:
            raise ValueError("Toda posición debe incluir stop loss obligatorio")
        if tp_mode == sl_mode and tp_value > 0 and sl_value >= tp_value:
            raise ValueError("Stop loss debe ser menor al take profit cuando usan la misma unidad")
        if sl_mode == "percent" and sl_value > 1.5:
            raise ValueError("Stop loss porcentual no puede superar 1.5%")
        if tp_value <= 0 and trailing_value <= 0:
            raise ValueError("Toda posición debe incluir take profit o trailing stop")
        return self


class TradeAmountMixin(BaseModel):
    trade_amount_mode: Literal["inherit", "fixed_usd", "balance_percent"] = "fixed_usd"
    amount_per_trade: float | None = Field(default=None, gt=0)
    amount_percentage: float | None = Field(default=None, gt=0, le=100)

    @model_validator(mode="after")
    def validate_trade_amount_rules(self):
        mode = str(getattr(self, "trade_amount_mode", "inherit") or "inherit").lower()
        amount = getattr(self, "amount_per_trade", None)
        percent = getattr(self, "amount_percentage", None)

        if mode == "fixed_usd" and (amount is None or float(amount) <= 0):
            raise ValueError("Debes indicar una cantidad por trade mayor a 0")
        if mode == "balance_percent" and (percent is None or float(percent) <= 0):
            raise ValueError("Debes indicar un porcentaje por trade mayor a 0")
        return self


class StrategyRequest(StrategyRiskMixin, TradeAmountMixin):
    connector_ids: list[int]
    market_type: MARKET_TYPES | None = None
    symbols: list[str]
    symbol_source_mode: Literal["manual", "dynamic"] = "manual"
    dynamic_symbol_limit: int = Field(default=10, ge=1, le=200)
    timeframe: str = "1h"
    strategy_slug: STRATEGY_LITERAL = "ema_rsi"
    risk_per_trade: float = Field(default=1, gt=0, le=100)
    min_ml_probability: float = Field(default=55, ge=0, le=100)
    use_live_if_available: bool = True
    take_profit_mode: Literal["percent", "usdt"] = "percent"
    take_profit_value: float = Field(default=1.5, gt=0)
    stop_loss_mode: Literal["percent", "usdt"] = "percent"
    stop_loss_value: float = Field(default=1.0, gt=0)
    trailing_stop_mode: Literal["percent", "usdt"] = "percent"
    trailing_stop_value: float = Field(default=0.8, gt=0)
    indicator_exit_enabled: bool = False
    indicator_exit_rule: Literal["macd_cross", "rsi_reversal", "ema_cross"] = "macd_cross"
    leverage_profile: Literal["conservative", "balanced", "aggressive", "none"] = "none"
    max_open_positions: int = Field(default=10, ge=1, le=20)
    compound_growth_enabled: bool = False
    atr_volatility_filter_enabled: bool = True


class BotSessionCreate(StrategyRiskMixin, TradeAmountMixin):
    connector_id: int
    session_name: str | None = Field(default=None, min_length=2, max_length=255)
    market_type: MARKET_TYPES | None = None
    symbols: list[str]
    symbol_source_mode: Literal["manual", "dynamic"] = "manual"
    dynamic_symbol_limit: int = Field(default=10, ge=1, le=200)
    timeframe: str = "5m"
    strategy_slug: STRATEGY_LITERAL = "ema_rsi"
    risk_per_trade: float = Field(default=1, gt=0, le=100)
    min_ml_probability: float = Field(default=55, ge=0, le=100)
    use_live_if_available: bool = True
    interval_minutes: int = Field(default=5, ge=1, le=1440)
    take_profit_mode: Literal["percent", "usdt"] = "percent"
    take_profit_value: float = Field(default=1.5, gt=0)
    stop_loss_mode: Literal["percent", "usdt"] = "percent"
    stop_loss_value: float = Field(default=1.0, gt=0)
    trailing_stop_mode: Literal["percent", "usdt"] = "percent"
    trailing_stop_value: float = Field(default=0.8, gt=0)
    indicator_exit_enabled: bool = False
    indicator_exit_rule: Literal["macd_cross", "rsi_reversal", "ema_cross"] = "macd_cross"
    leverage_profile: Literal["conservative", "balanced", "aggressive", "none"] = "none"
    max_open_positions: int = Field(default=10, ge=1, le=20)
    compound_growth_enabled: bool = False
    atr_volatility_filter_enabled: bool = True


class BotSessionUpdate(BaseModel):
    is_active: bool | None = None
    session_name: str | None = Field(default=None, min_length=2, max_length=255)
    trade_amount_mode: Literal["inherit", "fixed_usd", "balance_percent"] | None = None
    amount_per_trade: float | None = Field(default=None, gt=0)
    amount_percentage: float | None = Field(default=None, gt=0, le=100)
    market_type: MARKET_TYPES | None = None
    interval_minutes: int | None = Field(default=None, ge=1, le=1440)
    symbols: list[str] | None = None
    symbol_source_mode: Literal["manual", "dynamic"] | None = None
    dynamic_symbol_limit: int | None = Field(default=None, ge=1, le=200)
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
    leverage_profile: Literal["conservative", "balanced", "aggressive", "none"] | None = None
    max_open_positions: int | None = Field(default=None, ge=1, le=20)
    compound_growth_enabled: bool | None = None
    atr_volatility_filter_enabled: bool | None = None
    risk_per_trade: float | None = Field(default=None, gt=0, le=100)
    min_ml_probability: float | None = Field(default=None, ge=0, le=100)
    use_live_if_available: bool | None = None

    @model_validator(mode="after")
    def validate_partial_rules(self):
        mode = getattr(self, "trade_amount_mode", None)
        amount = getattr(self, "amount_per_trade", None)
        percent = getattr(self, "amount_percentage", None)
        if mode == "fixed_usd" and (amount is None or float(amount) <= 0):
            raise ValueError("Debes indicar una cantidad por trade mayor a 0")
        if mode == "balance_percent" and (percent is None or float(percent) <= 0):
            raise ValueError("Debes indicar un porcentaje por trade mayor a 0")
        tp_mode = getattr(self, "take_profit_mode", None)
        sl_mode = getattr(self, "stop_loss_mode", None)
        tp_value = getattr(self, "take_profit_value", None)
        sl_value = getattr(self, "stop_loss_value", None)
        trailing_value = getattr(self, "trailing_stop_value", None)
        if sl_value is not None and float(sl_value) <= 0:
            raise ValueError("Toda posición debe incluir stop loss obligatorio")
        if tp_value is not None and float(tp_value) <= 0 and trailing_value is not None and float(trailing_value) <= 0:
            raise ValueError("Toda posición debe incluir take profit o trailing stop")
        if tp_value is not None and sl_value is not None and tp_mode and sl_mode and tp_mode == sl_mode and float(sl_value) >= float(tp_value):
            raise ValueError("Stop loss debe ser menor al take profit cuando usan la misma unidad")
        if sl_mode == "percent" and sl_value is not None and float(sl_value) > 1.5:
            raise ValueError("Stop loss porcentual no puede superar 1.5%")
        return self


class BotSessionCopyPayload(BaseModel):
    connector_id: int | None = None
    symbols: list[str] | None = None


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


class StrategyTemplateCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str = ""
    is_public: bool = False
    source_bot_session_id: int | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class StrategyTemplateApplyPayload(BaseModel):
    connector_id: int
    symbols: list[str] = Field(default_factory=list)
    is_active: bool = True


class StrategyControlUpdate(BaseModel):
    allowed_strategies: list[str] = Field(default_factory=list)


class AdminUserUpdate(BaseModel):
    email: EmailStr | None = None
    name: str | None = Field(default=None, min_length=2, max_length=255)
    phone: str | None = Field(default=None, max_length=40)
    is_active: bool | None = None
    is_admin: bool | None = None
    alert_language: str | None = None
    telegram_alerts_enabled: bool | None = None
    telegram_bot_key: str | None = None
    telegram_chat_id: str | None = None


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


class AdminStrategyControlUpdate(BaseModel):
    managed_by_admin: bool
    allowed_strategies: list[str] = Field(default_factory=list)


class AdminPlanConfigPayload(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = ""
    apps: int = Field(default=1, ge=1)
    symbols: int = Field(default=5, ge=0)
    daily_movements: int = Field(default=10, ge=0)
    monthly_price_usd: float = Field(default=20.0, ge=0)
    is_custom: bool = False
    is_active: bool = True
    sort_order: int = 0


class AdminPricingConfigUpdate(BaseModel):
    base_commission_usd: float = Field(ge=0)
    cost_per_app_usd: float = Field(ge=0)
    cost_per_symbol_usd: float = Field(ge=0)
    cost_per_movement_usd: float = Field(ge=0)
    cost_per_gb_ram_usd: float = Field(ge=0)
    cost_per_gb_disk_usd: float = Field(ge=0)
    suggested_ram_per_app_gb: float = Field(ge=0)
    suggested_disk_per_app_gb: float = Field(ge=0)
