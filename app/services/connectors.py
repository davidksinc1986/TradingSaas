from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx

from app.security import decrypt_payload
from app.services.execution_guardrails import (
    ExecutionReferencePrice,
    MarketRules,
    build_validation_decision,
)

try:
    import ccxt
except Exception:
    ccxt = None

try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None


logger = logging.getLogger("trading_saas.execution")


@dataclass
class ExecutionResult:
    status: str
    message: str
    fill_price: float
    quantity: float
    raw: dict[str, Any]


class BaseConnectorClient:
    def __init__(self, connector):
        self.connector = connector
        self.secrets = decrypt_payload(connector.encrypted_secret_blob)
        self.config = connector.config_json or {}

    def resolve_market_rules(self, symbol: str) -> dict[str, Any]:
        return MarketRules(
            exchange=self.connector.platform,
            symbol=symbol,
            market_type=getattr(self.connector, "market_type", "spot"),
            raw_exchange_rules={},
            normalized_rule_source="base_connector_defaults",
        ).to_dict()

    def resolve_execution_reference_price(
        self,
        symbol: str,
        *,
        order_type: str = "market",
        side: str = "buy",
        analysis_price: float | None = None,
    ) -> dict[str, Any]:
        return ExecutionReferencePrice(
            value=float(analysis_price) if analysis_price is not None else None,
            source="analysis_price",
            used_fallback=True,
            details={"symbol": symbol, "order_type": order_type, "side": side},
        ).to_dict()

    def validate_and_adjust_order(
        self,
        symbol: str,
        *,
        market_type: str | None = None,
        order_type: str = "market",
        side: str = "buy",
        desired_qty: float,
        desired_price: float | None = None,
        risk_context: dict[str, Any] | None = None,
        connector_context: dict[str, Any] | None = None,
        analysis_price: float | None = None,
        quantity_semantics: str = "base",
    ) -> dict[str, Any]:
        execution_reference = self.resolve_execution_reference_price(
            symbol,
            order_type=order_type,
            side=side,
            analysis_price=analysis_price if analysis_price is not None else desired_price,
        )
        market_rules = self.resolve_market_rules(symbol)
        decision = build_validation_decision(
            exchange=self.connector.platform,
            symbol=symbol,
            market_type=(market_type or getattr(self.connector, "market_type", "spot") or "spot").lower(),
            order_type=order_type,
            side=side,
            desired_qty=desired_qty,
            desired_price=desired_price,
            analysis_price=analysis_price if analysis_price is not None else desired_price,
            execution_reference=ExecutionReferencePrice(**execution_reference),
            market_rules=MarketRules(**market_rules),
            risk_context=risk_context,
            connector_context=connector_context,
            quantity_semantics=quantity_semantics,
        )
        return decision.to_dict()

    def execute_market(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price_hint: float,
        reduce_only: bool = False,
        extra_params: dict[str, Any] | None = None,
        quantity_semantics: str = "base",
    ) -> ExecutionResult:
        return ExecutionResult(
            status="paper-filled",
            message="Paper execution completed",
            fill_price=price_hint,
            quantity=quantity,
            raw={
                "mode": self.connector.mode,
                "platform": self.connector.platform,
                "market_type": getattr(self.connector, "market_type", "spot"),
                "reduce_only": reduce_only,
                "quantity_semantics": quantity_semantics,
                "extra_params": extra_params or {},
            },
        )

    def normalize_symbol(self, symbol: str) -> dict[str, Any]:
        clean = (symbol or "").strip().upper()
        return {
            "input_symbol": symbol,
            "normalized_symbol": clean,
            "exchange_symbol": clean.replace("/", ""),
            "found": True,
        }

    def pretrade_validate(
        self,
        symbol: str,
        quantity: float,
        price_hint: float,
        *,
        side: str = "buy",
        order_type: str = "market",
        risk_context: dict[str, Any] | None = None,
        analysis_price: float | None = None,
        connector_context: dict[str, Any] | None = None,
        quantity_semantics: str = "base",
    ) -> dict[str, Any]:
        decision = self.validate_and_adjust_order(
            symbol,
            market_type=getattr(self.connector, "market_type", "spot"),
            order_type=order_type,
            side=side,
            desired_qty=quantity,
            desired_price=price_hint,
            risk_context=risk_context,
            connector_context=connector_context,
            analysis_price=analysis_price if analysis_price is not None else price_hint,
            quantity_semantics=quantity_semantics,
        )
        return {
            "ok": bool(decision["is_valid"]),
            "normalized_quantity": float(decision["normalized_qty"]),
            "normalized_price": float(decision["normalized_price"] or 0.0) if decision["normalized_price"] is not None else None,
            "reason_code": decision["skip_reason"] or "ok",
            "reason_message": decision["skip_reason"],
            "exchange_filters": {
                "amount_min": decision["amount_min"],
                "amount_step": decision["amount_step"],
                "price_step": decision["price_step"],
                "min_cost": decision["min_cost"],
                "final_cost": decision["final_cost"],
                **(decision.get("diagnostics") or {}),
            },
            "validation": decision,
        }

    def test_connection(self) -> dict[str, Any]:
        return {
            "ok": True,
            "platform": self.connector.platform,
            "mode": self.connector.mode,
            "market_type": getattr(self.connector, "market_type", "spot"),
        }

    def fetch_position_context(self, symbol: str) -> dict[str, Any]:
        return {
            "market_type": getattr(self.connector, "market_type", "spot"),
            "symbol": symbol,
            "has_position": False,
            "spot_base_free": 0.0,
            "spot_base_total": 0.0,
            "net_contracts": 0.0,
            "side": None,
        }

    def list_open_positions(self, symbols: list[str] | None = None) -> list[dict[str, Any]]:
        symbols = list(symbols or [])
        return [self.fetch_position_context(symbol) for symbol in symbols if symbol]

    def fetch_available_balance(self) -> dict[str, Any]:
        if self.connector.mode == "live":
            return {
                "ok": False,
                "mode": "live",
                "market_type": getattr(self.connector, "market_type", "spot"),
                "quote_asset": str((self.config or {}).get("quote_asset", "USDT")).upper(),
                "available_balance": 0.0,
                "total_balance": 0.0,
                "source": "unsupported_live_balance",
                "error": f"Live balance fetch is not implemented for connector platform={self.connector.platform}",
            }

        fallback = float((self.config or {}).get("paper_balance", 1000) or 1000)
        return {
            "ok": True,
            "mode": self.connector.mode,
            "market_type": getattr(self.connector, "market_type", "spot"),
            "quote_asset": "USDT",
            "available_balance": fallback,
            "total_balance": fallback,
            "source": "paper_hint",
        }

    def place_risk_orders(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_loss_price: float,
        take_profit_price: float,
        trailing_stop_mode: str = "percent",
        trailing_stop_value: float = 0.0,
        market_type: str = "spot",
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "note": "Risk orders are not supported by this connector in current mode",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "stop_loss_price": stop_loss_price,
            "take_profit_price": take_profit_price,
            "trailing_stop_mode": trailing_stop_mode,
            "trailing_stop_value": trailing_stop_value,
            "market_type": market_type,
        }

    def cancel_risk_orders(self, symbol: str) -> dict[str, Any]:
        return {"ok": True, "cancelled": 0, "symbol": symbol}

    def prepare_execution_environment(self, symbol: str, *, leverage_profile: str = "none") -> dict[str, Any]:
        return {
            "ok": True,
            "symbol": symbol,
            "market_type": getattr(self.connector, "market_type", "spot"),
            "mode": getattr(self.connector, "mode", "paper"),
            "applied": [],
            "warnings": [],
            "capabilities": {
                "time_sync": False,
                "margin_mode": False,
                "position_mode": False,
                "set_leverage": False,
                "internal_transfer": False,
                "websocket_market_data": False,
                "websocket_balance": False,
            },
        }


class BaseExchangeAdapter:
    def __init__(self, connector, config: dict[str, Any]):
        self.connector = connector
        self.config = config or {}

    @property
    def exchange_name(self) -> str:
        return str(getattr(self.connector, "platform", "unknown") or "unknown").lower()

    def build_market_rules(self, exchange, symbol: str, market: dict[str, Any] | None) -> MarketRules:
        market_type = (getattr(self.connector, "market_type", None) or self.config.get("market_type") or "spot").lower()
        limits = (market or {}).get("limits") or {}
        precision = (market or {}).get("precision") or {}
        amount_limits = limits.get("amount") or {}
        price_limits = limits.get("price") or {}
        cost_limits = limits.get("cost") or {}
        contract_size = (market or {}).get("contractSize") or (market or {}).get("contract_size") or 1

        return MarketRules(
            exchange=self.exchange_name,
            symbol=symbol,
            market_type=market_type,
            amount_min=self._safe_float(amount_limits.get("min")),
            amount_max=self._safe_float(amount_limits.get("max")),
            amount_step=self._step_from_precision(precision.get("amount")),
            price_min=self._safe_float(price_limits.get("min")),
            price_max=self._safe_float(price_limits.get("max")),
            price_step=self._step_from_precision(precision.get("price")),
            price_precision=self._safe_int(precision.get("price")),
            amount_precision=self._safe_int(precision.get("amount")),
            min_cost=self._safe_float(cost_limits.get("min")),
            max_cost=self._safe_float(cost_limits.get("max")),
            contract_size=self._safe_float(contract_size, 1.0),
            requires_cost_for_market_buy=bool((getattr(exchange, "options", {}) or {}).get("createMarketBuyOrderRequiresPrice")),
            qty_semantics="contracts" if market_type in {"futures", "perpetual", "swap"} and market and market.get("contract") else "base",
            normalized_rule_source="markets|limits|precision|adapter",
            raw_exchange_rules=(market or {}).get("info") or {},
        )

    def resolve_execution_reference_price(
        self,
        exchange,
        symbol: str,
        *,
        market: dict[str, Any] | None,
        market_type: str,
        order_type: str,
        side: str,
        analysis_price: float | None,
    ) -> ExecutionReferencePrice:
        details: dict[str, Any] = {"market_type": market_type, "symbol": symbol}
        best_bid = best_ask = None
        try:
            order_book = exchange.fetch_order_book(symbol, limit=5)
            bids = (order_book or {}).get("bids") or []
            asks = (order_book or {}).get("asks") or []
            best_bid = float(bids[0][0]) if bids else None
            best_ask = float(asks[0][0]) if asks else None
            details["order_book_top"] = {"bid": best_bid, "ask": best_ask}
        except Exception as exc:
            details["order_book_error"] = str(exc)

        try:
            ticker = exchange.fetch_ticker(symbol)
        except Exception as exc:
            details["ticker_error"] = str(exc)
            ticker = {}

        if market_type in {"futures", "perpetual", "swap"}:
            mark_candidates = [ticker.get("mark"), ticker.get("markPrice")]
            for candidate in mark_candidates:
                if candidate not in (None, "", 0, 0.0):
                    details["mark_price"] = float(candidate)
                    break

        preferred = None
        source = "analysis_price"
        if order_type.lower() == "market":
            if side.lower() == "buy":
                preferred = best_ask or ticker.get("ask")
                source = "order_book_ask" if best_ask else "ticker_ask"
            else:
                preferred = best_bid or ticker.get("bid")
                source = "order_book_bid" if best_bid else "ticker_bid"

        if preferred in (None, "", 0, 0.0):
            for key in ("mark", "markPrice", "last", "close", "bid", "ask"):
                candidate = ticker.get(key)
                if candidate not in (None, "", 0, 0.0):
                    preferred = candidate
                    source = f"ticker_{key}"
                    break

        if preferred in (None, "", 0, 0.0):
            preferred = analysis_price
            source = "analysis_price"

        return ExecutionReferencePrice(
            value=self._safe_float(preferred),
            source=source,
            used_fallback=source == "analysis_price",
            details=details,
        )

    def build_order_params(
        self,
        *,
        side: str,
        market_type: str,
        reduce_only: bool,
        validation: dict[str, Any],
        extra_params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        params = dict(extra_params or {})
        if market_type in {"futures", "perpetual", "swap"} and reduce_only:
            params["reduceOnly"] = True
        return params

    def translate_error(self, detail: str) -> str:
        message = str(detail or "").lower()
        if "-1013" in message or "filter failure" in message:
            return "exchange_filter_failure"
        if "-2010" in message:
            return "exchange_insufficient_balance"
        if "reduceonly" in message or "reduce only" in message:
            return "exchange_reduce_only_rejected"
        if "position side" in message or "positionside" in message or "hedge mode" in message:
            return "exchange_market_type_mismatch"
        if "min notional" in message or "notional" in message or "min cost" in message:
            return "exchange_min_cost_failed"
        if "min qty" in message or "lot_size" in message or "minimum amount" in message or "less than minimum" in message:
            return "exchange_amount_step_failed"
        if "precision" in message or "tick size" in message or "invalid price" in message:
            return "exchange_price_precision_failed"
        if "invalid quantity" in message or "invalid amount" in message:
            return "exchange_amount_step_failed"
        if "insufficient" in message and ("margin" in message or "balance" in message or "fund" in message):
            return "exchange_insufficient_balance"
        if "invalid symbol" in message or ("symbol" in message and "invalid" in message):
            return "exchange_symbol_invalid"
        if "timed out" in message or "timeout" in message or "temporarily unavailable" in message:
            return "exchange_timeout"
        if "network" in message or "connection" in message:
            return "exchange_network_error"
        return "exchange_rejected"

    @staticmethod
    def _safe_float(value: Any, fallback: float | None = None) -> float | None:
        try:
            return float(value)
        except Exception:
            return fallback

    @staticmethod
    def _safe_int(value: Any, fallback: int | None = None) -> int | None:
        try:
            return int(value)
        except Exception:
            return fallback

    @staticmethod
    def _step_from_precision(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            numeric = float(value)
        except Exception:
            return None
        if numeric == 0:
            return 1.0
        if numeric < 1:
            return numeric
        if float(numeric).is_integer():
            return 10 ** (-int(numeric))
        return numeric


class BinanceExchangeAdapter(BaseExchangeAdapter):
    def build_market_rules(self, exchange, symbol: str, market: dict[str, Any] | None) -> MarketRules:
        rules = super().build_market_rules(exchange, symbol, market)
        filters = (((market or {}).get("info") or {}).get("filters")) or []
        source_parts = {"markets", "limits", "precision", "adapter"}
        for item in filters:
            filter_type = str(item.get("filterType") or "").upper()
            if filter_type == "LOT_SIZE":
                rules.amount_min = self._safe_float(item.get("minQty"), rules.amount_min)
                rules.amount_max = self._safe_float(item.get("maxQty"), rules.amount_max)
                rules.amount_step = self._safe_float(item.get("stepSize"), rules.amount_step)
                source_parts.add("filters")
            elif filter_type == "MARKET_LOT_SIZE":
                rules.market_amount_max = self._safe_float(item.get("maxQty"), rules.market_amount_max)
                source_parts.add("filters")
            elif filter_type == "PRICE_FILTER":
                rules.price_min = self._safe_float(item.get("minPrice"), rules.price_min)
                rules.price_max = self._safe_float(item.get("maxPrice"), rules.price_max)
                rules.price_step = self._safe_float(item.get("tickSize"), rules.price_step)
                source_parts.add("filters")
            elif filter_type in {"MIN_NOTIONAL", "NOTIONAL"}:
                rules.min_cost = self._safe_float(item.get("minNotional") or item.get("notional"), rules.min_cost)
                source_parts.add("filters")
        if ((market or {}).get("info") or {}).get("quoteOrderQtyMarketAllowed"):
            rules.requires_cost_for_market_buy = False
        rules.normalized_rule_source = "|".join(sorted(source_parts))
        return rules

    def build_order_params(self, *, side: str, market_type: str, reduce_only: bool, validation: dict[str, Any], extra_params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = super().build_order_params(side=side, market_type=market_type, reduce_only=reduce_only, validation=validation, extra_params=extra_params)
        if market_type == "spot" and side.lower() == "buy" and validation.get("requires_cost_for_market_buy") and validation.get("market_buy_cost"):
            params.setdefault("quoteOrderQty", validation["market_buy_cost"])
        return params


class BybitExchangeAdapter(BaseExchangeAdapter):
    def build_market_rules(self, exchange, symbol: str, market: dict[str, Any] | None) -> MarketRules:
        rules = super().build_market_rules(exchange, symbol, market)
        info = (market or {}).get("info") or {}
        lot_filter = info.get("lotSizeFilter") or {}
        price_filter = info.get("priceFilter") or {}
        rules.amount_min = self._safe_float(lot_filter.get("minOrderQty") or lot_filter.get("minOrderAmt"), rules.amount_min)
        rules.amount_max = self._safe_float(lot_filter.get("maxOrderQty") or lot_filter.get("maxOrderAmt"), rules.amount_max)
        rules.amount_step = self._safe_float(lot_filter.get("qtyStep"), rules.amount_step)
        rules.price_min = self._safe_float(price_filter.get("minPrice"), rules.price_min)
        rules.price_max = self._safe_float(price_filter.get("maxPrice"), rules.price_max)
        rules.price_step = self._safe_float(price_filter.get("tickSize"), rules.price_step)
        rules.min_cost = self._safe_float(lot_filter.get("minNotionalValue") or lot_filter.get("minOrderValue"), rules.min_cost)
        rules.normalized_rule_source = "markets|limits|precision|adapter|filters"
        return rules


class OKXExchangeAdapter(BaseExchangeAdapter):
    pass


class CCXTConnectorClient(BaseConnectorClient):
    def __init__(self, connector):
        super().__init__(connector)
        self._markets_cache: dict[str, Any] | None = None
        self.adapter = self._build_adapter()

    def _build_adapter(self) -> BaseExchangeAdapter:
        platform = str(getattr(self.connector, "platform", "") or "").lower()
        if platform == "binance":
            return BinanceExchangeAdapter(self.connector, self.config)
        if platform == "bybit":
            return BybitExchangeAdapter(self.connector, self.config)
        if platform == "okx":
            return OKXExchangeAdapter(self.connector, self.config)
        return BaseExchangeAdapter(self.connector, self.config)

    def build_exchange(self):
        if ccxt is None:
            raise RuntimeError("ccxt is not installed")

        exchange_class = getattr(ccxt, self.connector.platform)
        request_timeout_ms = int((self.config or {}).get("request_timeout_ms") or 20000)
        kwargs = {
            "apiKey": self.secrets.get("api_key"),
            "secret": self.secrets.get("secret_key"),
            "enableRateLimit": True,
            "timeout": request_timeout_ms,
        }

        if self.connector.platform == "okx" and self.secrets.get("passphrase"):
            kwargs["password"] = self.secrets.get("passphrase")
        if self.secrets.get("password"):
            kwargs["password"] = self.secrets.get("password")

        options = {}
        market_type = (getattr(self.connector, "market_type", None) or self.config.get("market_type") or "spot").lower()

        recv_window = int((self.config or {}).get("recv_window_ms") or 10000)
        if self.connector.platform in {"binance", "bybit", "okx"}:
            options["defaultType"] = "future" if market_type == "futures" else "spot"
            options["adjustForTimeDifference"] = bool((self.config or {}).get("adjust_for_time_difference", True))
            options["recvWindow"] = recv_window
        if self.connector.platform == "bybit" and market_type == "futures":
            options.setdefault("fetchCurrencies", False)

        if self.config.get("sandbox"):
            options["sandboxMode"] = True

        if options:
            kwargs["options"] = options

        exchange = exchange_class(kwargs)

        if self.config.get("sandbox") and hasattr(exchange, "set_sandbox_mode"):
            exchange.set_sandbox_mode(True)

        return exchange

    def _time_sync_enabled(self) -> bool:
        return bool((self.config or {}).get("adjust_for_time_difference", True))

    def _resolve_leverage(self, leverage_profile: str) -> int | None:
        explicit = (self.config or {}).get("futures_leverage")
        if explicit not in (None, ""):
            try:
                return max(int(explicit), 1)
            except Exception:
                return None
        profile = str(leverage_profile or (self.config or {}).get("leverage_profile") or "none").lower()
        mapping = {
            "none": 1,
            "conservative": 2,
            "balanced": 3,
            "aggressive": 5,
        }
        return mapping.get(profile, 1)

    def _resolve_margin_mode(self) -> str:
        return str((self.config or {}).get("futures_margin_mode") or "isolated").lower()

    def _resolve_position_mode(self) -> str:
        return str((self.config or {}).get("futures_position_mode") or "oneway").lower()

    def _resolve_retry_attempts(self) -> int:
        raw = (self.config or {}).get("retry_attempts")
        if raw in (None, ""):
            return 2
        return max(int(raw), 1)

    def _resolve_retry_delay_ms(self) -> int:
        raw = (self.config or {}).get("retry_delay_ms")
        if raw in (None, ""):
            return 350
        return max(int(raw), 0)

    def _sync_exchange_clock(self, exchange) -> dict[str, Any]:
        result = {"enabled": self._time_sync_enabled(), "applied": False, "source": None, "server_time": None, "time_difference_ms": None}
        if not result["enabled"]:
            return result

        if hasattr(exchange, "load_time_difference"):
            try:
                exchange.load_time_difference()
                result["applied"] = True
                result["source"] = "load_time_difference"
                result["time_difference_ms"] = getattr(exchange, "timeDifference", None)
                return result
            except Exception as exc:
                result["warning"] = str(exc)

        if hasattr(exchange, "fetch_time"):
            try:
                server_time = exchange.fetch_time()
                result["server_time"] = server_time
                result["time_difference_ms"] = int(server_time - (time.time() * 1000))
                result["applied"] = True
                result["source"] = "fetch_time"
            except Exception as exc:
                result["warning"] = str(exc)
        return result

    def prepare_execution_environment(self, symbol: str, *, leverage_profile: str = "none") -> dict[str, Any]:
        market_type = (getattr(self.connector, "market_type", None) or self.config.get("market_type") or "spot").lower()
        margin_mode = self._resolve_margin_mode()
        position_mode = self._resolve_position_mode()
        resolved_leverage_profile = str(leverage_profile or (self.config or {}).get("leverage_profile") or "none").lower()
        leverage = self._resolve_leverage(leverage_profile)
        result = {
            "ok": True,
            "symbol": symbol,
            "market_type": market_type,
            "mode": self.connector.mode,
            "recv_window_ms": int((self.config or {}).get("recv_window_ms") or 10000),
            "request_timeout_ms": int((self.config or {}).get("request_timeout_ms") or 20000),
            "retry_attempts": self._resolve_retry_attempts(),
            "retry_delay_ms": self._resolve_retry_delay_ms(),
            "futures_margin_mode": margin_mode,
            "futures_position_mode": position_mode,
            "futures_leverage": leverage,
            "leverage_profile": resolved_leverage_profile,
            "applied": [],
            "warnings": [],
            "capabilities": {
                "time_sync": self._time_sync_enabled(),
                "margin_mode": False,
                "position_mode": False,
                "set_leverage": False,
                "internal_transfer": False,
                "websocket_market_data": False,
                "websocket_balance": False,
                "rate_limit_enabled": True,
            },
        }

        if self.connector.mode != "live":
            result["warnings"].append("paper_mode_environment")
            return result

        exchange = self.build_exchange()
        result["capabilities"]["internal_transfer"] = bool(hasattr(exchange, "transfer"))
        result["rate_limit_ms"] = getattr(exchange, "rateLimit", None)
        result["capabilities"]["websocket_market_data"] = bool(hasattr(exchange, "watch_order_book") or hasattr(exchange, "watch_ticker"))
        result["capabilities"]["websocket_balance"] = bool(hasattr(exchange, "watch_balance"))

        time_sync = self._sync_exchange_clock(exchange)
        result["time_sync"] = time_sync
        if time_sync.get("applied"):
            result["applied"].append("time_sync")
        elif time_sync.get("enabled"):
            result["warnings"].append("time_sync_unavailable")

        try:
            market = self._market(exchange, symbol)
            result["market_found"] = bool(market)
            result["market_rules"] = self.adapter.build_market_rules(exchange, symbol, market).to_dict() if market else {"symbol": symbol, "found": False}
        except Exception as exc:
            result["ok"] = False
            result["warnings"].append(f"market_rules_unavailable:{exc}")
            return result

        if market_type != "futures":
            return result

        result["futures_settings"] = {
            "margin_mode": margin_mode,
            "position_mode": position_mode,
            "leverage": leverage,
            "leverage_profile": resolved_leverage_profile,
        }

        if hasattr(exchange, "set_margin_mode"):
            try:
                exchange.set_margin_mode(margin_mode.upper(), symbol)
                result["applied"].append(f"margin_mode:{margin_mode}")
                result["capabilities"]["margin_mode"] = True
            except Exception as exc:
                result["warnings"].append(f"margin_mode:{exc}")

        hedged = position_mode in {"hedge", "hedged", "both"}
        if hasattr(exchange, "set_position_mode"):
            try:
                exchange.set_position_mode(hedged, symbol)
                result["applied"].append(f"position_mode:{'hedge' if hedged else 'oneway'}")
                result["capabilities"]["position_mode"] = True
            except TypeError:
                try:
                    exchange.set_position_mode(hedged)
                    result["applied"].append(f"position_mode:{'hedge' if hedged else 'oneway'}")
                    result["capabilities"]["position_mode"] = True
                except Exception as exc:
                    result["warnings"].append(f"position_mode:{exc}")
            except Exception as exc:
                result["warnings"].append(f"position_mode:{exc}")

        if leverage and leverage > 0 and hasattr(exchange, "set_leverage"):
            try:
                exchange.set_leverage(leverage, symbol)
                result["applied"].append(f"leverage:{leverage}")
                result["capabilities"]["set_leverage"] = True
            except Exception as exc:
                result["warnings"].append(f"leverage:{exc}")

        return result

    def _load_markets(self, exchange) -> dict[str, Any]:
        if self._markets_cache is None:
            self._markets_cache = exchange.load_markets()
        return self._markets_cache

    def _market(self, exchange, symbol: str) -> dict[str, Any] | None:
        markets = self._load_markets(exchange)
        return markets.get(symbol)

    def resolve_market_rules(self, symbol: str) -> dict[str, Any]:
        exchange = self.build_exchange()
        market = self._market(exchange, symbol)
        rules = self.adapter.build_market_rules(exchange, symbol, market)
        return rules.to_dict()

    def resolve_execution_reference_price(
        self,
        symbol: str,
        *,
        order_type: str = "market",
        side: str = "buy",
        analysis_price: float | None = None,
    ) -> dict[str, Any]:
        exchange = self.build_exchange()
        market = self._market(exchange, symbol)
        market_type = (getattr(self.connector, "market_type", None) or self.config.get("market_type") or "spot").lower()
        return self.adapter.resolve_execution_reference_price(
            exchange,
            symbol,
            market=market,
            market_type=market_type,
            order_type=order_type,
            side=side,
            analysis_price=analysis_price,
        ).to_dict()

    def normalize_symbol(self, symbol: str) -> dict[str, Any]:
        exchange = self.build_exchange()
        markets = self._load_markets(exchange)
        candidate = (symbol or "").strip().upper()

        alt = candidate.replace("/", "")
        # First check if the candidate (with or without slashes) is directly in markets
        if candidate in markets:
            market = markets[candidate]
            return {
                "input_symbol": symbol,
                "normalized_symbol": candidate,
                "exchange_symbol": market.get("id") or alt,
                "found": True,
            }

        if alt in markets:
            market = markets[alt]
            return {
                "input_symbol": symbol,
                "normalized_symbol": alt,
                "exchange_symbol": market.get("id") or alt,
                "found": True,
            }

        # Handle missing slashes if not found directly
        if "/" not in candidate and self.connector.platform in {"binance", "bybit", "okx"}:
            for quote in ["USDT", "USDC", "BTC", "ETH", "EUR", "DAI", "BUSD"]:
                if candidate.endswith(quote):
                    try_symbol = candidate[:-len(quote)] + "/" + quote
                    if try_symbol in markets:
                        market = markets[try_symbol]
                        return {
                            "input_symbol": symbol,
                            "normalized_symbol": try_symbol,
                            "exchange_symbol": market.get("id") or alt,
                            "found": True,
                        }

        # Original loop as fallback
        for market_symbol, market in markets.items():
            if (market.get("id") or "").upper() == alt:
                return {
                    "input_symbol": symbol,
                    "normalized_symbol": market_symbol,
                    "exchange_symbol": market.get("id") or alt,
                    "found": True,
                }

        return {
            "input_symbol": symbol,
            "normalized_symbol": candidate,
            "exchange_symbol": alt,
            "found": False,
        }

    def fetch_available_balance(self) -> dict[str, Any]:
        if self.connector.mode != "live":
            return super().fetch_available_balance()

        exchange = self.build_exchange()
        market_type = (getattr(self.connector, "market_type", None) or self.config.get("market_type") or "spot").lower()
        quote_asset = str(self.config.get("quote_asset", "USDT")).upper()

        try:
            balance = exchange.fetch_balance()
        except Exception as exc:
            return {
                "ok": False,
                "mode": "live",
                "market_type": market_type,
                "quote_asset": quote_asset,
                "available_balance": 0.0,
                "total_balance": 0.0,
                "source": "exchange_fetch_failed",
                "error": str(exc),
            }

        if market_type == "spot":
            asset_row = (balance or {}).get(quote_asset) or {}
            free_balance = float(asset_row.get("free") or 0.0)
            total_balance = float(asset_row.get("total") or free_balance or 0.0)

            return {
                "ok": True,
                "mode": "live",
                "market_type": "spot",
                "quote_asset": quote_asset,
                "available_balance": free_balance,
                "total_balance": total_balance,
                "source": "exchange_spot_balance",
            }

        free_bucket = (balance or {}).get("free") or {}
        total_bucket = (balance or {}).get("total") or {}
        info = (balance or {}).get("info") or {}

        free_balance = float(free_bucket.get(quote_asset) or 0.0)
        total_balance = float(total_bucket.get(quote_asset) or free_balance or 0.0)

        if free_balance <= 0:
            for key in ("availableBalance", "available_balance", "walletBalance", "wallet_balance"):
                raw = info.get(key)
                if raw is not None:
                    try:
                        free_balance = float(raw)
                        break
                    except Exception:
                        pass

        if total_balance <= 0:
            for key in ("totalWalletBalance", "walletBalance", "equity", "marginBalance"):
                raw = info.get(key)
                if raw is not None:
                    try:
                        total_balance = float(raw)
                        break
                    except Exception:
                        pass

        if total_balance <= 0:
            total_balance = free_balance

        return {
            "ok": True,
            "mode": "live",
            "market_type": "futures",
            "quote_asset": quote_asset,
            "available_balance": float(free_balance),
            "total_balance": float(total_balance),
            "source": "exchange_futures_balance",
        }

    def validate_and_adjust_order(
        self,
        symbol: str,
        *,
        market_type: str | None = None,
        order_type: str = "market",
        side: str = "buy",
        desired_qty: float,
        desired_price: float | None = None,
        risk_context: dict[str, Any] | None = None,
        connector_context: dict[str, Any] | None = None,
        analysis_price: float | None = None,
        quantity_semantics: str = "base",
    ) -> dict[str, Any]:
        decision = build_validation_decision(
            exchange=self.connector.platform,
            symbol=symbol,
            market_type=(market_type or getattr(self.connector, "market_type", "spot") or "spot").lower(),
            order_type=order_type,
            side=side,
            desired_qty=desired_qty,
            desired_price=desired_price,
            analysis_price=analysis_price if analysis_price is not None else desired_price,
            execution_reference=ExecutionReferencePrice(**self.resolve_execution_reference_price(
                symbol,
                order_type=order_type,
                side=side,
                analysis_price=analysis_price if analysis_price is not None else desired_price,
            )),
            market_rules=MarketRules(**self.resolve_market_rules(symbol)),
            risk_context=risk_context,
            connector_context=connector_context,
            quantity_semantics=quantity_semantics,
        )
        return decision.to_dict()

    @staticmethod
    def _is_auxiliary_heartbeat_error(detail: str) -> bool:
        message = str(detail or "").lower()
        return any(
            fragment in message
            for fragment in (
                "/v5/asset/coin/query-info",
                "asset/coin/query-info",
                "coin/query-info",
            )
        )

    def _normalize_amount(self, exchange, symbol: str, quantity: float) -> float:
        try:
            return float(exchange.amount_to_precision(symbol, quantity))
        except Exception:
            return float(quantity)

    def _normalize_price(self, exchange, symbol: str, price: float) -> float:
        try:
            return float(exchange.price_to_precision(symbol, price))
        except Exception:
            return float(price)

    def _categorize_exchange_error(self, detail: str) -> str:
        return self.adapter.translate_error(detail)

    def _raise_order_rejection(
        self,
        *,
        exc: Exception,
        symbol: str,
        side: str,
        quantity: float,
        normalized_price: float,
        reduce_only: bool,
        order_params: dict[str, Any],
        scope: str,
    ) -> None:
        category = self._categorize_exchange_error(str(exc))
        detail = str(exc).strip() or exc.__class__.__name__
        raise RuntimeError(
            f"{scope} rejected by exchange "
            f"[category={category}] "
            f"[symbol={symbol}] "
            f"[side={side}] "
            f"[quantity={float(quantity):.12f}] "
            f"[price_hint={float(normalized_price):.12f}] "
            f"[reduce_only={str(bool(reduce_only)).lower()}] "
            f"[params={order_params}] "
            f"detail={detail}"
        ) from exc

    def min_requirements(self, symbol: str) -> dict[str, Any]:
        exchange = self.build_exchange()
        market = self._market(exchange, symbol)
        if not market:
            return {"symbol": symbol, "found": False}
        return {
            "symbol": symbol,
            "found": True,
            "base": market.get("base"),
            "quote": market.get("quote"),
            **self.resolve_market_rules(symbol),
        }

    def fetch_position_context(self, symbol: str) -> dict[str, Any]:
        exchange = self.build_exchange()
        market = self._market(exchange, symbol)
        market_type = (getattr(self.connector, "market_type", None) or self.config.get("market_type") or "spot").lower()

        if not market:
            return {
                "market_type": market_type,
                "symbol": symbol,
                "found": False,
                "has_position": False,
                "spot_base_free": 0.0,
                "spot_base_total": 0.0,
                "net_contracts": 0.0,
                "side": None,
            }

        if market_type == "spot":
            try:
                balance = exchange.fetch_balance()
            except Exception as exc:
                return {"ok": False, "error": f"balance fetch failed: {exc}"}
            ticker = {}
            try:
                ticker = exchange.fetch_ticker(symbol)
            except Exception:
                ticker = {}
            base = market.get("base")
            asset_row = (balance or {}).get(base) or {}
            free_qty = float(asset_row.get("free") or 0.0)
            total_qty = float(asset_row.get("total") or free_qty or 0.0)

            return {
                "market_type": "spot",
                "symbol": symbol,
                "found": True,
                "base": base,
                "quote": market.get("quote"),
                "has_position": total_qty > 0,
                "spot_base_free": free_qty,
                "spot_base_total": total_qty,
                "net_contracts": 0.0,
                "side": "long" if total_qty > 0 else None,
                "last_price": float(ticker.get("last") or ticker.get("close") or 0.0),
            }

        try:
            positions = exchange.fetch_positions([symbol])
        except Exception as exc:
            return {"ok": False, "error": f"positions fetch failed: {exc}"}

        net_contracts = 0.0
        detected_side = None

        for pos in positions or []:
            info = pos.get("info") or {}
            raw_amt = (
                pos.get("contracts")
                or pos.get("positionAmt")
                or info.get("positionAmt")
                or info.get("contracts")
                or 0
            )
            try:
                amt = float(raw_amt or 0.0)
            except Exception:
                amt = 0.0

            side = (pos.get("side") or info.get("positionSide") or "").lower()
            if side == "short" and amt > 0:
                amt = -amt

            if abs(amt) > 0:
                net_contracts += amt

        if net_contracts > 0:
            detected_side = "long"
        elif net_contracts < 0:
            detected_side = "short"

        entry_price = 0.0
        mark_price = 0.0
        for pos in positions or []:
            info = pos.get("info") or {}
            if symbol != pos.get("symbol", symbol):
                pass
            entry_price = float(pos.get("entryPrice") or info.get("entryPrice") or info.get("avgPrice") or entry_price or 0.0)
            mark_price = float(pos.get("markPrice") or info.get("markPrice") or info.get("mark_price") or mark_price or 0.0)
            if entry_price or mark_price:
                break

        return {
            "market_type": "futures",
            "symbol": symbol,
            "found": True,
            "base": market.get("base"),
            "quote": market.get("quote"),
            "has_position": net_contracts != 0,
            "spot_base_free": 0.0,
            "spot_base_total": 0.0,
            "net_contracts": float(net_contracts),
            "side": detected_side,
            "entry_price": entry_price,
            "mark_price": mark_price,
            "last_price": mark_price,
        }

    def list_open_positions(self, symbols: list[str] | None = None) -> list[dict[str, Any]]:
        market_type = (getattr(self.connector, "market_type", None) or self.config.get("market_type") or "spot").lower()
        exchange = self.build_exchange()
        symbols = [str(symbol).strip() for symbol in (symbols or []) if str(symbol).strip()]

        if market_type == "spot":
            return [self.fetch_position_context(symbol) for symbol in symbols]

        try:
            positions = exchange.fetch_positions(symbols or None)
        except Exception:
            positions = []

        results: list[dict[str, Any]] = []
        for pos in positions or []:
            info = pos.get("info") or {}
            raw_symbol = pos.get("symbol") or info.get("symbol")
            if not raw_symbol:
                continue
            raw_amt = pos.get("contracts") or pos.get("positionAmt") or info.get("positionAmt") or info.get("contracts") or 0
            try:
                amt = float(raw_amt or 0.0)
            except Exception:
                amt = 0.0
            side = (pos.get("side") or info.get("positionSide") or "").lower()
            if side == "short" and amt > 0:
                amt = -amt
            if amt == 0:
                continue
            results.append({
                "market_type": market_type,
                "symbol": raw_symbol,
                "has_position": True,
                "net_contracts": amt,
                "side": "long" if amt > 0 else "short",
                "entry_price": float(pos.get("entryPrice") or info.get("entryPrice") or info.get("avgPrice") or 0.0),
                "mark_price": float(pos.get("markPrice") or info.get("markPrice") or info.get("mark_price") or 0.0),
                "last_price": float(pos.get("markPrice") or info.get("markPrice") or info.get("mark_price") or 0.0),
                "spot_base_total": 0.0,
                "spot_base_free": 0.0,
            })
        return results

    def _resolve_fill_price(self, order: dict[str, Any], price_hint: float) -> float:
        average = order.get("average")
        price = order.get("price")
        if average is not None:
            return float(average)
        if price is not None:
            return float(price)

        cost = order.get("cost")
        amount = order.get("amount")
        try:
            if cost is not None and amount not in (None, 0, 0.0):
                return float(cost) / float(amount)
        except Exception:
            pass

        return float(price_hint)

    def _order_status_to_result(self, order: dict[str, Any]) -> str:
        status = str(order.get("status") or "").lower()
        if status in {"closed", "filled"}:
            return "live-filled"
        if status in {"open", "new"}:
            return "live-submitted"
        return "live-submitted"

    def execute_market(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price_hint: float,
        reduce_only: bool = False,
        extra_params: dict[str, Any] | None = None,
        quantity_semantics: str = "base",
    ) -> ExecutionResult:
        if self.connector.mode != "live":
            return super().execute_market(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price_hint=price_hint,
                reduce_only=reduce_only,
                extra_params=extra_params,
                quantity_semantics=quantity_semantics,
            )

        exchange = self.build_exchange()
        market_type = (getattr(self.connector, "market_type", None) or self.config.get("market_type") or "spot").lower()
        validation = self.validate_and_adjust_order(
            symbol,
            market_type=market_type,
            order_type="market",
            side=side,
            desired_qty=quantity,
            desired_price=price_hint,
            analysis_price=price_hint,
            risk_context={"allow_adjust_up": False},
            connector_context={
                "price_guardrails": (self.config or {}).get("price_guardrails") or {},
                "connector_mode": self.connector.mode,
            },
            quantity_semantics=quantity_semantics,
        )

        if not validation.get("is_valid"):
            reason = validation.get("skip_reason") or "pretrade_rejected"
            raise RuntimeError(
                f"market_order rejected locally "
                f"[reason={reason}] "
                f"[symbol={symbol}] "
                f"[side={side}] "
                f"[validation={validation}]"
            )

        quantity = float(validation["normalized_qty"])
        normalized_price = float(validation["normalized_price"] or price_hint)
        order_params = self.adapter.build_order_params(
            side=side,
            market_type=market_type,
            reduce_only=reduce_only,
            validation=validation,
            extra_params=extra_params,
        )
        retry_attempts = self._resolve_retry_attempts()
        retry_delay_ms = self._resolve_retry_delay_ms()
        idempotency_key = f"{self.connector.platform}-{getattr(self.connector, 'id', 'na')}-{uuid4().hex[:20]}"
        order_params.setdefault("clientOrderId", idempotency_key)
        order_params.setdefault("newClientOrderId", idempotency_key)

        logger.info(
            "order_preflight %s",
            json.dumps(
                {
                    "exchange": self.connector.platform,
                    "connector_id": getattr(self.connector, "id", None),
                    "symbol": symbol,
                    "market_type": market_type,
                    "side": side,
                    "order_type": "market",
                    "analysis_price": price_hint,
                    "execution_reference_price": validation.get("execution_reference_price"),
                    "raw_qty": quantity,
                    "normalized_qty": validation.get("normalized_qty"),
                    "raw_price": price_hint,
                    "normalized_price": validation.get("normalized_price"),
                    "amount_min": validation.get("amount_min"),
                    "amount_step": validation.get("amount_step"),
                    "price_step": validation.get("price_step"),
                    "min_cost": validation.get("min_cost"),
                    "final_cost": validation.get("final_cost"),
                    "contract_size": validation.get("contract_size"),
                    "decision": "send",
                    "risk_blocked": validation.get("risk_blocked"),
                    "requires_cost_for_market_buy": validation.get("requires_cost_for_market_buy"),
                    "retry_attempts": retry_attempts,
                    "client_order_id": idempotency_key,
                },
                ensure_ascii=False,
            ),
        )

        order = None
        last_exc: Exception | None = None
        for attempt in range(1, retry_attempts + 1):
            try:
                if order_params:
                    order = exchange.create_order(
                        symbol=symbol,
                        type="market",
                        side=side,
                        amount=quantity,
                        params=order_params,
                    )
                else:
                    order = exchange.create_order(
                        symbol=symbol,
                        type="market",
                        side=side,
                        amount=quantity,
                    )
                break
            except Exception as exc:
                last_exc = exc
                category = self._categorize_exchange_error(str(exc))
                retryable = category in {"exchange_timeout", "exchange_network_error"}
                logger.warning(
                    "market_order_attempt_failed %s",
                    json.dumps(
                        {
                            "exchange": self.connector.platform,
                            "symbol": symbol,
                            "side": side,
                            "attempt": attempt,
                            "retry_attempts": retry_attempts,
                            "category": category,
                            "retryable": retryable,
                            "client_order_id": idempotency_key,
                            "detail": str(exc),
                        },
                        ensure_ascii=False,
                    ),
                )
                if not retryable or attempt >= retry_attempts:
                    break
                if retry_delay_ms > 0:
                    time.sleep(retry_delay_ms / 1000.0)

        if order is None and last_exc is not None:
            self._raise_order_rejection(
                exc=last_exc,
                symbol=symbol,
                side=side,
                quantity=quantity,
                normalized_price=normalized_price,
                reduce_only=reduce_only,
                order_params=order_params,
                scope="market_order",
            )

        fill_price = self._resolve_fill_price(order, price_hint)
        result_status = self._order_status_to_result(order)

        return ExecutionResult(
            status=result_status,
            message="Live order submitted via CCXT",
            fill_price=fill_price,
            quantity=float(order.get("amount") or quantity),
            raw={
                **order,
                "validation": validation,
                "reduce_only": reduce_only,
                "extra_params": order_params,
            },
        )

    def cancel_risk_orders(self, symbol: str) -> dict[str, Any]:
        if self.connector.mode != "live":
            return {"ok": True, "cancelled": 0, "symbol": symbol, "mode": self.connector.mode}

        exchange = self.build_exchange()
        market_type = (getattr(self.connector, "market_type", None) or self.config.get("market_type") or "spot").lower()
        if market_type != "futures":
            return {"ok": True, "cancelled": 0, "symbol": symbol, "market_type": market_type}

        cancelled = 0
        errors: list[str] = []

        try:
            open_orders = exchange.fetch_open_orders(symbol)
        except Exception as exc:
            return {"ok": False, "cancelled": 0, "symbol": symbol, "error": str(exc)}

        for order in open_orders or []:
            order_type = str(order.get("type") or "").lower()
            info = order.get("info") or {}
            type_hint = str(info.get("type") or "").upper()

            is_risk_order = (
                "stop" in order_type
                or "take_profit" in order_type
                or "TAKE_PROFIT" in type_hint
                or "STOP" in type_hint
            )
            if not is_risk_order:
                continue

            try:
                exchange.cancel_order(order["id"], symbol)
                cancelled += 1
            except Exception as exc:
                errors.append(str(exc))

        return {"ok": len(errors) == 0, "cancelled": cancelled, "symbol": symbol, "errors": errors}

    def place_risk_orders(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_loss_price: float,
        take_profit_price: float,
        trailing_stop_mode: str = "percent",
        trailing_stop_value: float = 0.0,
        market_type: str = "spot",
    ) -> dict[str, Any]:
        if self.connector.mode != "live":
            return {
                "ok": True,
                "mode": self.connector.mode,
                "note": "paper mode - no live risk orders placed",
            }

        if market_type != "futures":
            return {
                "ok": True,
                "market_type": market_type,
                "note": "risk orders are only placed automatically for futures in this implementation",
            }

        exchange = self.build_exchange()

        qty = self._normalize_amount(exchange, symbol, quantity)
        stop_loss_price = self._normalize_price(exchange, symbol, stop_loss_price)
        take_profit_price = self._normalize_price(exchange, symbol, take_profit_price)

        if qty <= 0:
            raise RuntimeError(f"Risk order quantity resolved to 0 for {symbol}")

        closing_side = "sell" if str(side).lower() == "buy" else "buy"
        created_orders: list[dict[str, Any]] = []

        # STOP LOSS
        sl_params = {
            "stopPrice": stop_loss_price,
            "reduceOnly": True,
            "workingType": "MARK_PRICE",
        }
        try:
            sl_order = exchange.create_order(
                symbol=symbol,
                type="STOP_MARKET",
                side=closing_side,
                amount=qty,
                price=None,
                params=sl_params,
            )
        except Exception as exc:
            self._raise_order_rejection(
                exc=exc,
                symbol=symbol,
                side=closing_side,
                quantity=qty,
                normalized_price=stop_loss_price,
                reduce_only=True,
                order_params=sl_params,
                scope="stop_loss_order",
            )
        created_orders.append({
            "kind": "stop_loss",
            "id": sl_order.get("id"),
            "type": sl_order.get("type"),
            "status": sl_order.get("status"),
            "stop_price": stop_loss_price,
            "raw": sl_order,
        })

        # TAKE PROFIT
        tp_params = {
            "stopPrice": take_profit_price,
            "reduceOnly": True,
            "workingType": "MARK_PRICE",
        }
        try:
            tp_order = exchange.create_order(
                symbol=symbol,
                type="TAKE_PROFIT_MARKET",
                side=closing_side,
                amount=qty,
                price=None,
                params=tp_params,
            )
        except Exception as exc:
            self._raise_order_rejection(
                exc=exc,
                symbol=symbol,
                side=closing_side,
                quantity=qty,
                normalized_price=take_profit_price,
                reduce_only=True,
                order_params=tp_params,
                scope="take_profit_order",
            )
        created_orders.append({
            "kind": "take_profit",
            "id": tp_order.get("id"),
            "type": tp_order.get("type"),
            "status": tp_order.get("status"),
            "stop_price": take_profit_price,
            "raw": tp_order,
        })

        # Trailing stop:
        # lo dejamos documentado pero no creamos orden live aquí porque la implementación varía
        # mucho entre exchanges y puede romper compatibilidad. TP/SL ya quedan cubiertos.
        trailing_info = {
            "requested": bool(trailing_stop_value and trailing_stop_value > 0),
            "mode": trailing_stop_mode,
            "value": trailing_stop_value,
            "placed_live": False,
            "note": "Trailing stop not placed as exchange order in this implementation",
        }

        return {
            "ok": True,
            "symbol": symbol,
            "market_type": market_type,
            "side": side,
            "closing_side": closing_side,
            "quantity": qty,
            "orders": created_orders,
            "trailing": trailing_info,
        }

    def test_connection(self) -> dict[str, Any]:
        if self.connector.mode != "live":
            return {"ok": True, "mode": self.connector.mode, "note": "paper/signal mode"}

        exchange = self.build_exchange()
        warnings: list[str] = []
        try:
            markets = exchange.load_markets()
        except Exception as exc:
            if self.connector.platform == "bybit" and self._is_auxiliary_heartbeat_error(str(exc)):
                warnings.append(f"auxiliary_asset_info_unavailable:{exc}")
                options = getattr(exchange, "options", {}) or {}
                options["fetchCurrencies"] = False
                exchange.options = options
                try:
                    markets = exchange.load_markets()
                except Exception as exc2:
                    warnings.append(f"markets_load_retry_failed:{exc2}")
                    markets = {} # Fallback to empty instead of crashing heartbeat
            else:
                raise
        balance = None
        ok = True
        try:
            balance = exchange.fetch_balance()
        except Exception as exc:
            if self.connector.platform == "bybit" and self._is_auxiliary_heartbeat_error(str(exc)):
                warnings.append(f"auxiliary_asset_info_unavailable:{exc}")
                balance = {"warning": str(exc), "auxiliary": True}
            else:
                balance = {"error": str(exc)}
                ok = False

        return {
            "ok": ok,
            "platform": self.connector.platform,
            "markets_loaded": len(markets),
            "balance_preview": balance,
            "warnings": warnings,
        }


class MT5ConnectorClient(BaseConnectorClient):
    def fetch_position_context(self, symbol: str) -> dict[str, Any]:
        if self.connector.mode != "live":
            return super().fetch_position_context(symbol)

        self._ensure_session()
        try:
            positions = mt5.positions_get(symbol=symbol) or []
            net_volume = 0.0
            side = None
            entry_price = 0.0
            last_price = 0.0
            for item in positions:
                data = item._asdict() if hasattr(item, "_asdict") else {}
                volume = float(data.get("volume") or getattr(item, "volume", 0.0) or 0.0)
                pos_type = int(data.get("type") or getattr(item, "type", 0) or 0)
                signed = volume if pos_type == getattr(mt5, "POSITION_TYPE_BUY", 0) else -volume
                net_volume += signed
                entry_price = float(data.get("price_open") or getattr(item, "price_open", 0.0) or entry_price or 0.0)
                last_price = float(data.get("price_current") or getattr(item, "price_current", 0.0) or last_price or 0.0)
            if net_volume > 0:
                side = "long"
            elif net_volume < 0:
                side = "short"
            return {
                "market_type": getattr(self.connector, "market_type", "forex"),
                "symbol": symbol,
                "found": True,
                "has_position": net_volume != 0,
                "spot_base_free": 0.0,
                "spot_base_total": 0.0,
                "net_contracts": float(net_volume),
                "side": side,
                "entry_price": entry_price,
                "last_price": last_price,
            }
        finally:
            self._shutdown()

    def list_open_positions(self, symbols: list[str] | None = None) -> list[dict[str, Any]]:
        if self.connector.mode != "live":
            return super().list_open_positions(symbols)

        self._ensure_session()
        try:
            positions = mt5.positions_get() or []
            results = []
            allowed = {str(symbol).strip() for symbol in (symbols or []) if str(symbol).strip()}
            for item in positions:
                data = item._asdict() if hasattr(item, "_asdict") else {}
                symbol = data.get("symbol") or getattr(item, "symbol", None)
                if not symbol or (allowed and symbol not in allowed):
                    continue
                volume = float(data.get("volume") or getattr(item, "volume", 0.0) or 0.0)
                pos_type = int(data.get("type") or getattr(item, "type", 0) or 0)
                signed = volume if pos_type == getattr(mt5, "POSITION_TYPE_BUY", 0) else -volume
                if signed == 0:
                    continue
                results.append({
                    "market_type": getattr(self.connector, "market_type", "forex"),
                    "symbol": symbol,
                    "has_position": True,
                    "net_contracts": float(signed),
                    "side": "long" if signed > 0 else "short",
                    "entry_price": float(data.get("price_open") or getattr(item, "price_open", 0.0) or 0.0),
                    "last_price": float(data.get("price_current") or getattr(item, "price_current", 0.0) or 0.0),
                    "ticket": data.get("ticket") or getattr(item, "ticket", None),
                    "spot_base_total": 0.0,
                    "spot_base_free": 0.0,
                })
            return results
        finally:
            self._shutdown()
    def fetch_available_balance(self) -> dict[str, Any]:
        if self.connector.mode != "live":
            return super().fetch_available_balance()

        self._ensure_session()
        try:
            account = mt5.account_info()
            if account is None:
                raise RuntimeError(f"mt5.account_info failed: {mt5.last_error()}")

            currency = str(getattr(account, "currency", None) or self.config.get("quote_asset") or "USD").upper()
            available_balance = float(getattr(account, "margin_free", None) or getattr(account, "equity", None) or getattr(account, "balance", 0.0) or 0.0)
            total_balance = float(getattr(account, "equity", None) or getattr(account, "balance", None) or available_balance or 0.0)

            return {
                "ok": True,
                "mode": "live",
                "market_type": getattr(self.connector, "market_type", "spot"),
                "quote_asset": currency,
                "available_balance": available_balance,
                "total_balance": total_balance,
                "source": "mt5_account_info",
                "login": getattr(account, "login", None),
                "server": getattr(account, "server", None),
            }
        finally:
            self._shutdown()

    def _ensure_session(self):
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package is not available in this environment")

        path = self.config.get("terminal_path")
        login = self.secrets.get("login") or self.config.get("login")
        password = self.secrets.get("password")
        server = self.secrets.get("server") or self.config.get("server")

        initialized = mt5.initialize(path=path) if path else mt5.initialize()
        if not initialized:
            raise RuntimeError(f"mt5.initialize failed: {mt5.last_error()}")

        if login and password and server:
            authorized = mt5.login(login=int(login), password=str(password), server=str(server))
            if not authorized:
                raise RuntimeError(f"mt5.login failed: {mt5.last_error()}")

    def _shutdown(self):
        if mt5 is not None:
            try:
                mt5.shutdown()
            except Exception:
                pass

    def _market_price(self, symbol: str, side: str, price_hint: float) -> float:
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return price_hint
        return float(tick.ask if side == "buy" else tick.bid or price_hint)

    def execute_market(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price_hint: float,
        reduce_only: bool = False,
        extra_params: dict[str, Any] | None = None,
        quantity_semantics: str = "base",
    ) -> ExecutionResult:
        if self.connector.mode != "live":
            return super().execute_market(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price_hint=price_hint,
                reduce_only=reduce_only,
                extra_params=extra_params,
                quantity_semantics=quantity_semantics,
            )

        self._ensure_session()
        try:
            if not mt5.symbol_select(symbol, True):
                raise RuntimeError(f"symbol_select failed for {symbol}: {mt5.last_error()}")

            order_type = mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL
            fill_type = getattr(mt5, self.config.get("type_filling", "ORDER_FILLING_IOC"), mt5.ORDER_FILLING_IOC)
            price = self._market_price(symbol, side, price_hint)

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(quantity),
                "type": order_type,
                "price": price,
                "deviation": int(self.config.get("deviation", 20)),
                "magic": int(self.config.get("magic", 260311)),
                "comment": self.config.get("comment", "quant-suite"),
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": fill_type,
            }

            stop_pct = float(self.config.get("stop_pct", 0) or 0)
            take_pct = float(self.config.get("take_pct", 0) or 0)

            if stop_pct > 0:
                request["sl"] = price * (1 - stop_pct) if side == "buy" else price * (1 + stop_pct)
            if take_pct > 0:
                request["tp"] = price * (1 + take_pct) if side == "buy" else price * (1 - take_pct)

            result = mt5.order_send(request)
            if result is None:
                raise RuntimeError(f"mt5.order_send returned None: {mt5.last_error()}")

            retcode = getattr(result, "retcode", None)
            if retcode != mt5.TRADE_RETCODE_DONE:
                raise RuntimeError(f"mt5 order rejected retcode={retcode} last_error={mt5.last_error()}")

            result_dict = result._asdict() if hasattr(result, "_asdict") else {"retcode": retcode}

            return ExecutionResult(
                status="live-filled",
                message="Live order submitted via MetaTrader5",
                fill_price=float(getattr(result, "price", price) or price),
                quantity=float(getattr(result, "volume", quantity) or quantity),
                raw={**result_dict, "reduce_only": reduce_only, "extra_params": extra_params or {}},
            )
        finally:
            self._shutdown()

    def test_connection(self) -> dict[str, Any]:
        self._ensure_session()
        try:
            account = mt5.account_info()
            if account is None:
                raise RuntimeError(f"mt5.account_info failed: {mt5.last_error()}")
            account_dict = account._asdict() if hasattr(account, "_asdict") else {"login": getattr(account, "login", None)}
            return {"ok": True, "account": account_dict}
        finally:
            self._shutdown()


class TradingViewConnectorClient(BaseConnectorClient):
    def fetch_available_balance(self) -> dict[str, Any]:
        return {
            "ok": False,
            "mode": self.connector.mode,
            "market_type": getattr(self.connector, "market_type", "spot"),
            "quote_asset": str((self.config or {}).get("quote_asset", "USDT")).upper(),
            "available_balance": 0.0,
            "total_balance": 0.0,
            "source": "signal_only_connector",
            "error": "TradingView is signal-only and does not expose an executable account balance",
        }

    def test_connection(self) -> dict[str, Any]:
        return {
            "ok": True,
            "platform": "tradingview",
            "note": "Use /api/webhooks/tradingview as webhook URL and configure a passphrase if desired.",
        }


class CTraderConnectorClient(BaseConnectorClient):
    def _bridge_url(self) -> str | None:
        return self.config.get("bridge_url") or self.secrets.get("bridge_url")

    def fetch_available_balance(self) -> dict[str, Any]:
        if self.connector.mode != "live":
            return super().fetch_available_balance()

        bridge_url = self._bridge_url()
        if not bridge_url:
            return {
                "ok": False,
                "mode": "live",
                "market_type": getattr(self.connector, "market_type", "spot"),
                "quote_asset": str((self.config or {}).get("quote_asset", "USD")).upper(),
                "available_balance": 0.0,
                "total_balance": 0.0,
                "source": "ctrader_bridge_missing",
                "error": "cTrader live balance requires a bridge endpoint that exposes account data",
            }

        errors: list[str] = []
        with httpx.Client(timeout=10.0) as client:
            for endpoint in ("/account", "/balance"):
                try:
                    response = client.get(bridge_url.rstrip("/") + endpoint)
                    response.raise_for_status()
                    data = response.json()
                    available_balance = float(
                        data.get("available_balance")
                        or data.get("free_margin")
                        or data.get("freeBalance")
                        or data.get("balance")
                        or 0.0
                    )
                    total_balance = float(
                        data.get("total_balance")
                        or data.get("equity")
                        or data.get("balance")
                        or available_balance
                        or 0.0
                    )
                    return {
                        "ok": True,
                        "mode": "live",
                        "market_type": getattr(self.connector, "market_type", "spot"),
                        "quote_asset": str(data.get("currency") or self.config.get("quote_asset") or "USD").upper(),
                        "available_balance": available_balance,
                        "total_balance": total_balance,
                        "source": f"ctrader_bridge{endpoint}",
                        "raw": data,
                    }
                except Exception as exc:
                    errors.append(f"{endpoint}: {exc}")

        return {
            "ok": False,
            "mode": "live",
            "market_type": getattr(self.connector, "market_type", "spot"),
            "quote_asset": str((self.config or {}).get("quote_asset", "USD")).upper(),
            "available_balance": 0.0,
            "total_balance": 0.0,
            "source": "ctrader_bridge_balance_unavailable",
            "error": "; ".join(errors) or "Bridge did not return account balance data",
        }

    def execute_market(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price_hint: float,
        reduce_only: bool = False,
        extra_params: dict[str, Any] | None = None,
        quantity_semantics: str = "base",
    ) -> ExecutionResult:
        if self.connector.mode != "live":
            return super().execute_market(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price_hint=price_hint,
                reduce_only=reduce_only,
                extra_params=extra_params,
                quantity_semantics=quantity_semantics,
            )

        bridge_url = self._bridge_url()
        if not bridge_url:
            return ExecutionResult(
                status="bridge-required",
                message="cTrader live mode requires a bridge_url or a dedicated Open API client implementation.",
                fill_price=price_hint,
                quantity=quantity,
                raw={"platform": "ctrader", "reduce_only": reduce_only, "extra_params": extra_params or {}},
            )

        payload = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price_hint": price_hint,
            "reduce_only": reduce_only,
            "extra_params": extra_params or {},
            "access_token": self.secrets.get("access_token"),
            "account_id": self.secrets.get("account_id"),
            "client_id": self.secrets.get("client_id"),
            "client_secret": self.secrets.get("client_secret"),
        }

        with httpx.Client(timeout=20.0) as client:
            response = client.post(bridge_url.rstrip("/") + "/execute", json=payload)
            response.raise_for_status()
            data = response.json()

        return ExecutionResult(
            status=data.get("status", "live-submitted"),
            message=data.get("message", "cTrader bridge order submitted"),
            fill_price=float(data.get("fill_price", price_hint)),
            quantity=float(data.get("quantity", quantity)),
            raw=data,
        )

    def test_connection(self) -> dict[str, Any]:
        bridge_url = self._bridge_url()
        if not bridge_url:
            return {"ok": True, "note": "No bridge_url configured yet; cTrader remains ready for bridge mode."}

        with httpx.Client(timeout=10.0) as client:
            response = client.get(bridge_url.rstrip("/") + "/health")
            response.raise_for_status()
            return {"ok": True, "bridge": response.json()}


def get_client(connector):
    if connector.platform in {"binance", "bybit", "okx"}:
        return CCXTConnectorClient(connector)
    if connector.platform == "mt5":
        return MT5ConnectorClient(connector)
    if connector.platform == "ctrader":
        return CTraderConnectorClient(connector)
    if connector.platform == "tradingview":
        return TradingViewConnectorClient(connector)
    return BaseConnectorClient(connector)
