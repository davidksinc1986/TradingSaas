from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.db import commit_with_retry, flush_with_retry
from app.security import decrypt_payload
from app.services.connector_state import build_runtime_connector, ensure_connector_market_type_state, resolve_runtime_market_type

try:
    import ccxt
except Exception:
    ccxt = None

try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None


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

    def execute_market(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price_hint: float,
        reduce_only: bool = False,
        extra_params: dict[str, Any] | None = None,
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

    def pretrade_validate(self, symbol: str, quantity: float, price_hint: float) -> dict[str, Any]:
        return {
            "ok": quantity > 0,
            "normalized_quantity": float(quantity),
            "normalized_price": float(price_hint),
            "reason_code": "ok" if quantity > 0 else "rejected_invalid_quantity",
            "exchange_filters": {},
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

    def fetch_available_balance(self) -> dict[str, Any]:
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


class CCXTConnectorClient(BaseConnectorClient):
    def __init__(self, connector):
        super().__init__(connector)
        self._markets_cache: dict[str, Any] | None = None

    def build_exchange(self):
        if ccxt is None:
            raise RuntimeError("ccxt is not installed")

        exchange_class = getattr(ccxt, self.connector.platform)
        kwargs = {
            "apiKey": self.secrets.get("api_key"),
            "secret": self.secrets.get("secret_key"),
            "enableRateLimit": True,
        }

        if self.connector.platform == "okx" and self.secrets.get("passphrase"):
            kwargs["password"] = self.secrets.get("passphrase")
        if self.secrets.get("password"):
            kwargs["password"] = self.secrets.get("password")

        options = {}
        market_type = (getattr(self.connector, "market_type", None) or self.config.get("market_type") or "spot").lower()

        if self.connector.platform in {"binance", "bybit", "okx"}:
            options["defaultType"] = "future" if market_type == "futures" else "spot"

        if self.config.get("sandbox"):
            options["sandboxMode"] = True

        if options:
            kwargs["options"] = options

        exchange = exchange_class(kwargs)

        if self.config.get("sandbox") and hasattr(exchange, "set_sandbox_mode"):
            exchange.set_sandbox_mode(True)

        return exchange

    def _load_markets(self, exchange) -> dict[str, Any]:
        if self._markets_cache is None:
            self._markets_cache = exchange.load_markets()
        return self._markets_cache

    def _market(self, exchange, symbol: str) -> dict[str, Any] | None:
        markets = self._load_markets(exchange)
        return markets.get(symbol)

    def normalize_symbol(self, symbol: str) -> dict[str, Any]:
        exchange = self.build_exchange()
        markets = self._load_markets(exchange)
        candidate = (symbol or "").strip().upper()

        if candidate in markets:
            market = markets[candidate]
            return {
                "input_symbol": symbol,
                "normalized_symbol": candidate,
                "exchange_symbol": market.get("id") or candidate.replace("/", ""),
                "found": True,
            }

        alt = candidate.replace("/", "")
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

        balance = exchange.fetch_balance()

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

    def pretrade_validate(self, symbol: str, quantity: float, price_hint: float) -> dict[str, Any]:
        exchange = self.build_exchange()
        market = self._market(exchange, symbol)
        normalized_qty, normalized_price, min_notional = self._apply_exchange_filters(exchange, symbol, quantity, price_hint)

        exchange_filters = {
            "min_notional": float(min_notional),
            "min_qty": float(((market or {}).get("limits") or {}).get("amount", {}).get("min") or 0.0),
            "step_size": float(((market or {}).get("precision") or {}).get("amount") or 0.0),
            "tick_size": float(((market or {}).get("precision") or {}).get("price") or 0.0),
        }

        if normalized_qty <= 0:
            return {
                "ok": False,
                "normalized_quantity": float(normalized_qty),
                "normalized_price": float(normalized_price),
                "reason_code": "rejected_invalid_quantity",
                "exchange_filters": exchange_filters,
            }

        min_qty = exchange_filters["min_qty"]
        if min_qty > 0 and normalized_qty < min_qty:
            return {
                "ok": False,
                "normalized_quantity": float(normalized_qty),
                "normalized_price": float(normalized_price),
                "reason_code": "skipped_min_qty",
                "exchange_filters": exchange_filters,
            }

        notional = normalized_qty * max(normalized_price, 0.0000001)
        if min_notional > 0 and notional < min_notional:
            return {
                "ok": False,
                "normalized_quantity": float(normalized_qty),
                "normalized_price": float(normalized_price),
                "reason_code": "skipped_min_notional",
                "exchange_filters": exchange_filters,
            }

        return {
            "ok": True,
            "normalized_quantity": float(normalized_qty),
            "normalized_price": float(normalized_price),
            "reason_code": "ok",
            "exchange_filters": exchange_filters,
        }

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

    def _min_notional(self, market: dict[str, Any] | None) -> float:
        if not market:
            return 0.0
        limits = market.get("limits") or {}
        cost = limits.get("cost") or {}
        min_cost = cost.get("min")
        try:
            return float(min_cost or 0.0)
        except Exception:
            return 0.0

    def _apply_exchange_filters(self, exchange, symbol: str, quantity: float, price_hint: float) -> tuple[float, float, float]:
        market = self._market(exchange, symbol)
        quantity = self._normalize_amount(exchange, symbol, quantity)
        normalized_price = self._normalize_price(exchange, symbol, price_hint)
        min_notional = self._min_notional(market)

        if min_notional > 0 and quantity * normalized_price < min_notional:
            min_quantity = min_notional / max(normalized_price, 0.0000001)
            quantity = self._normalize_amount(exchange, symbol, min_quantity)

        return quantity, normalized_price, min_notional

    def min_requirements(self, symbol: str) -> dict[str, Any]:
        exchange = self.build_exchange()
        market = self._market(exchange, symbol)
        if not market:
            return {"symbol": symbol, "found": False}

        limits = market.get("limits") or {}
        amount_limits = limits.get("amount") or {}
        price_limits = limits.get("price") or {}

        return {
            "symbol": symbol,
            "found": True,
            "base": market.get("base"),
            "quote": market.get("quote"),
            "min_qty": float(amount_limits.get("min") or 0.0),
            "min_price": float(price_limits.get("min") or 0.0),
            "min_notional": self._min_notional(market),
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
            balance = exchange.fetch_balance()
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
            }

        try:
            positions = exchange.fetch_positions([symbol])
        except Exception:
            positions = []

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

            if amt != 0:
                net_contracts += amt

        if net_contracts > 0:
            detected_side = "long"
        elif net_contracts < 0:
            detected_side = "short"

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
        }

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

    def execute_market(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price_hint: float,
        reduce_only: bool = False,
        extra_params: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        if self.connector.mode != "live":
            return super().execute_market(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price_hint=price_hint,
                reduce_only=reduce_only,
                extra_params=extra_params,
            )

        exchange = self.build_exchange()
        quantity, normalized_price, min_notional = self._apply_exchange_filters(exchange, symbol, quantity, price_hint)

        if quantity <= 0:
            raise RuntimeError(f"Quantity for {symbol} resolved to 0 after exchange precision filters")

        order_params = dict(extra_params or {})
        market_type = (getattr(self.connector, "market_type", None) or self.config.get("market_type") or "spot").lower()

        if market_type == "futures" and reduce_only:
            order_params["reduceOnly"] = True

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

        fill_price = self._resolve_fill_price(order, price_hint)

        return ExecutionResult(
            status="live-submitted",
            message="Live order submitted via CCXT",
            fill_price=fill_price,
            quantity=float(order.get("amount") or quantity),
            raw={
                **order,
                "normalized_price": normalized_price,
                "min_notional": min_notional,
                "reduce_only": reduce_only,
                "extra_params": order_params,
            },
        )

    def test_connection(self) -> dict[str, Any]:
        if self.connector.mode != "live":
            return {"ok": True, "mode": self.connector.mode, "note": "paper/signal mode"}

        exchange = self.build_exchange()
        markets = exchange.load_markets()
        balance = None
        try:
            balance = exchange.fetch_balance()
        except Exception as exc:
            balance = {"error": str(exc)}

        return {
            "ok": True,
            "platform": self.connector.platform,
            "markets_loaded": len(markets),
            "balance_preview": balance,
        }


class MT5ConnectorClient(BaseConnectorClient):
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
    ) -> ExecutionResult:
        if self.connector.mode != "live":
            return super().execute_market(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price_hint=price_hint,
                reduce_only=reduce_only,
                extra_params=extra_params,
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
                status="live-submitted",
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
    def test_connection(self) -> dict[str, Any]:
        return {
            "ok": True,
            "platform": "tradingview",
            "note": "Use /api/webhooks/tradingview as webhook URL and configure a passphrase if desired.",
        }


class CTraderConnectorClient(BaseConnectorClient):
    def _bridge_url(self) -> str | None:
        return self.config.get("bridge_url") or self.secrets.get("bridge_url")

    def execute_market(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price_hint: float,
        reduce_only: bool = False,
        extra_params: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        if self.connector.mode != "live":
            return super().execute_market(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price_hint=price_hint,
                reduce_only=reduce_only,
                extra_params=extra_params,
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


def _safe_float(value: Any, fallback: float = 0.0) -> float:
    try:
        parsed = float(value)
        if parsed != parsed:
            return fallback
        return parsed
    except Exception:
        return fallback


def _percent_to_decimal(value: float) -> float:
    clean = _safe_float(value, 0.0)
    return clean / 100 if clean > 1 else clean


def _compute_exit_prices(
    *,
    signal: str,
    entry_price: float,
    take_profit_mode: str,
    take_profit_value: float,
    stop_loss_mode: str,
    stop_loss_value: float,
) -> tuple[float, float, float]:
    tp_delta = entry_price * _percent_to_decimal(take_profit_value) if take_profit_mode == "percent" else float(take_profit_value)
    sl_delta = entry_price * _percent_to_decimal(stop_loss_value) if stop_loss_mode == "percent" else float(stop_loss_value)

    if signal == "buy":
        take_profit_price = entry_price + tp_delta
        stop_loss_price = max(entry_price - sl_delta, 0.0000001)
    else:
        take_profit_price = max(entry_price - tp_delta, 0.0000001)
        stop_loss_price = entry_price + sl_delta

    stop_pct = abs(entry_price - stop_loss_price) / max(entry_price, 0.0000001)
    return stop_loss_price, take_profit_price, max(stop_pct, 0.0001)


def _candle_payload(df) -> dict[str, Any]:
    if df.empty:
        return {}
    row = df.iloc[-1]
    ts = row["timestamp"]
    if hasattr(ts, "to_pydatetime"):
        ts = ts.to_pydatetime()
    return {
        "timestamp": ts.isoformat(),
        "open": _safe_float(row.get("open")),
        "high": _safe_float(row.get("high")),
        "low": _safe_float(row.get("low")),
        "close": _safe_float(row.get("close")),
        "volume": _safe_float(row.get("volume")),
    }


def _analysis_frame(frame, market_health: dict[str, Any] | None) -> tuple[Any, dict[str, Any]]:
    health = market_health or {}
    if frame.empty:
        return frame, {
            "used_confirmed_only": False,
            "dropped_unconfirmed_candle": False,
            "dropped_rows": 0,
        }

    if not health.get("has_unconfirmed_candle") or len(frame.index) <= 1:
        return frame, {
            "used_confirmed_only": False,
            "dropped_unconfirmed_candle": False,
            "dropped_rows": 0,
        }

    confirmed = frame.iloc[:-1].copy()
    return confirmed, {
        "used_confirmed_only": True,
        "dropped_unconfirmed_candle": True,
        "dropped_rows": 1,
        "reason": "analysis_uses_last_closed_candle",
    }


def _signal_diagnostics(data) -> dict[str, Any]:
    if data.empty:
        return {}
    from app.services.indicators import add_indicators

    enriched = add_indicators(data.copy())
    if enriched.empty:
        return {}
    row = enriched.iloc[-1]
    return {
        "ret_1": _safe_float(row.get("ret_1")),
        "ret_5": _safe_float(row.get("ret_5")),
        "vol_10": _safe_float(row.get("vol_10")),
        "adx": _safe_float(row.get("adx")),
        "ema_fast": _safe_float(row.get("ema_fast")),
        "ema_slow": _safe_float(row.get("ema_slow")),
        "rsi": _safe_float(row.get("rsi")),
        "atr": _safe_float(row.get("atr")),
        "atr_mean_20": _safe_float(row.get("atr_mean_20")),
        "hh_20": _safe_float(row.get("hh_20")),
        "ll_20": _safe_float(row.get("ll_20")),
    }


def _primary_reason(decision_reasons: list[str]) -> str:
    if not decision_reasons:
        return "ok"
    priority = [
        "invalid_symbol",
        "missing_market_data",
        "balance_unavailable",
        "strategy_market_mismatch",
        "max_open_positions",
        "spot_sell_without_inventory",
        "short_disabled",
        "low_confidence",
        "strategy_hold",
        "last_candle_not_confirmed",
    ]
    for item in priority:
        if item in decision_reasons:
            return item
    return decision_reasons[0]


def _reason_details(decision_reasons: list[str], notes: dict[str, Any]) -> list[dict[str, Any]]:
    signal_context = notes.get("signal_context") or {}
    market_quality = notes.get("market_quality") or {}
    pretrade = notes.get("pretrade") or {}
    risk_plan = notes.get("risk_plan") or {}
    details_map: dict[str, str] = {
        "missing_market_data": "No se encontró OHLCV utilizable para analizar el símbolo.",
        "last_candle_not_confirmed": "Se evitó operar porque la última vela todavía no cerró.",
        "strategy_market_mismatch": "La estrategia seleccionada no está habilitada para este tipo de mercado.",
        "invalid_symbol": "El exchange no reconoció el símbolo configurado para este conector.",
        "strategy_hold": "La estrategia no encontró una entrada o salida válida en la última vela confirmada.",
        "low_confidence": "La probabilidad ML quedó por debajo del umbral mínimo configurado.",
        "max_open_positions": "Se alcanzó el número máximo de posiciones abiertas permitidas.",
        "spot_sell_without_inventory": "En spot no había inventario disponible para vender.",
        "short_disabled": "La estrategia no permite abrir cortos nuevos en futures.",
        "balance_unavailable": "No fue posible consultar el balance real/paper del conector.",
        "exchange_environment_not_ready": "No se pudo preparar correctamente el entorno del exchange antes de operar.",
        "rejected_invalid_quantity": "La cantidad calculada terminó en cero o fuera del paso mínimo del exchange.",
        "skipped_min_qty": "La cantidad no cumple el tamaño mínimo del mercado.",
        "skipped_min_notional": "El nocional final quedó por debajo del mínimo exigido por el exchange.",
        "market_price_mismatch": "El precio de referencia para ejecutar difiere demasiado del precio analizado.",
        "suspicious_price_scale_detected": "El precio del exchange parece desescalado o inconsistente frente al análisis.",
        "risk_engine_blocked": "El motor de riesgo bloqueó la operación por límites de exposición.",
        "max_open_positions_reached": "El motor de riesgo bloqueó la operación por exceso de posiciones abiertas.",
        "market_data_anomaly": "El motor de riesgo detectó anomalías en los datos de mercado.",
    }
    details: list[dict[str, Any]] = []
    for code in decision_reasons:
        detail: dict[str, Any] = {"code": code, "message": details_map.get(code, code.replace("_", " "))}
        if code == "low_confidence":
            detail["context"] = {
                "ml_probability": notes.get("ml_probability_decimal"),
                "min_ml_probability": notes.get("min_ml_probability"),
            }
        elif code in {"strategy_hold", "market_data_anomaly"}:
            detail["context"] = {
                "signal_context": signal_context,
                "market_health": market_quality.get("health") or {},
            }
        elif code.startswith("skipped_") or code.startswith("rejected_") or code in {"market_price_mismatch", "suspicious_price_scale_detected"}:
            detail["context"] = {
                "reason_message": pretrade.get("reason_message"),
                "exchange_filters": pretrade.get("exchange_filters") or {},
            }
        elif code in {"risk_engine_blocked", "max_open_positions_reached"}:
            detail["context"] = risk_plan
        elif code == "exchange_environment_not_ready":
            detail["context"] = notes.get("execution_environment") or {}
        details.append(detail)
    return details


def _status_from_reasons(decision_reasons: list[str], *, default: str = "skipped") -> str:
    if not decision_reasons:
        return default
    primary = _primary_reason(decision_reasons)
    return f"skipped_{primary}"[:30]


def _annotate_decision(notes: dict[str, Any], decision_reasons: list[str], *, decision: str) -> None:
    primary = _primary_reason(decision_reasons)
    notes["decision_reasons"] = list(decision_reasons)
    notes["decision_summary"] = {
        "decision": decision,
        "primary_reason": primary,
        "reason_codes": list(decision_reasons),
        "reason_details": _reason_details(decision_reasons, notes),
    }


def _resolve_trade_amount_config(
    user,
    *,
    trade_amount_mode: str | None = None,
    fixed_trade_amount_usd: float | None = None,
    trade_balance_percent: float | None = None,
) -> dict[str, float | str]:
    mode = str(trade_amount_mode or getattr(user, "trade_amount_mode", "fixed_usd") or "fixed_usd").lower()
    if mode == "balance_percent":
        return {
            "mode": "balance_percent",
            "fixed_trade_amount_usd": 0.0,
            "trade_balance_percent": _safe_float(
                trade_balance_percent if trade_balance_percent is not None else getattr(user, "trade_balance_percent", 10.0),
                10.0,
            ),
        }
    return {
        "mode": "fixed_usd",
        "fixed_trade_amount_usd": _safe_float(
            fixed_trade_amount_usd if fixed_trade_amount_usd is not None else getattr(user, "fixed_trade_amount_usd", 10.0),
            10.0,
        ),
        "trade_balance_percent": 0.0,
    }


def _trade_amount_cap(
    user,
    available_balance: float,
    price: float,
    *,
    trade_amount_mode: str | None = None,
    fixed_trade_amount_usd: float | None = None,
    trade_balance_percent: float | None = None,
) -> float:
    sizing = _resolve_trade_amount_config(
        user,
        trade_amount_mode=trade_amount_mode,
        fixed_trade_amount_usd=fixed_trade_amount_usd,
        trade_balance_percent=trade_balance_percent,
    )
    mode = str(sizing["mode"]).lower()
    if mode == "balance_percent":
        budget = available_balance * (_safe_float(sizing["trade_balance_percent"], 10.0) / 100.0)
    else:
        budget = _safe_float(sizing["fixed_trade_amount_usd"], 10.0)
    if available_balance > 0:
        budget = min(max(budget, 10.0), available_balance)
    return max(budget / max(price, 0.0000001), 0.0)


def _resolve_order_price_context(
    *,
    client,
    symbol: str,
    signal: str,
    analysis_price: float,
    market_meta: dict[str, Any],
) -> dict[str, Any]:
    exchange_price = _safe_float((market_meta or {}).get("exchange_price"), 0.0)
    execution_reference: dict[str, Any] = {}
    try:
        execution_reference = client.resolve_execution_reference_price(
            symbol,
            order_type="market",
            side=signal,
            analysis_price=analysis_price,
        )
    except Exception as exc:
        execution_reference = {
            "value": None,
            "source": "execution_reference_unavailable",
            "used_fallback": True,
            "details": {"error": str(exc)},
        }

    execution_price = _safe_float(execution_reference.get("value"), 0.0)
    resolved_price = execution_price or exchange_price or analysis_price
    return {
        "analysis_price": analysis_price,
        "exchange_price": exchange_price or None,
        "execution_reference": execution_reference,
        "resolved_price": resolved_price,
        "resolved_source": execution_reference.get("source") if execution_price else ("exchange_price" if exchange_price else "analysis_price"),
    }


def sync_positions_with_exchange(db, connector, symbols: list[str] | None = None) -> dict[str, Any]:
    from app.services.position_lifecycle import reconcile_positions_with_exchange

    result = reconcile_positions_with_exchange(db, connector, close_orphans=True)
    result["symbols_checked"] = sorted({*(symbols or []), *[item.get("symbol") for item in result.get("resolved", []) if item.get("symbol")]})
    result["inconsistencies"] = len(result.get("orphaned") or []) + len([
        item for item in result.get("resolved", []) if item.get("action") != "matched"
    ])
    return result


def run_strategy(
    *,
    db,
    user_id: int,
    connector_ids: list[int],
    symbols: list[str],
    timeframe: str,
    strategy_slug: str,
    risk_per_trade: float,
    min_ml_probability: float,
    use_live_if_available: bool,
    take_profit_mode: str = "percent",
    take_profit_value: float = 1.5,
    stop_loss_mode: str = "percent",
    stop_loss_value: float = 1.0,
    trailing_stop_mode: str = "percent",
    trailing_stop_value: float = 0.0,
    indicator_exit_enabled: bool = False,
    indicator_exit_rule: str = "macd_cross",
    leverage_profile: str = "none",
    max_open_positions: int = 1,
    compound_growth_enabled: bool = False,
    atr_volatility_filter_enabled: bool = True,
    symbol_source_mode: str = "manual",
    dynamic_symbol_limit: int | None = None,
    run_source: str = "manual",
    bot_session_id: int | None = None,
    market_type: str | None = None,
    trade_amount_mode: str | None = None,
    fixed_trade_amount_usd: float | None = None,
    trade_balance_percent: float | None = None,
):
    import json

    from app.models import BotSession, Connector, OpenPosition, TradeLog, TradeRun, User
    from app.services.alerts import (
        format_user_execution_message,
        format_user_failure_message,
        send_admin_user_alert_sync,
    )
    from app.services.connectors import BaseConnectorClient, get_client as get_connector_client
    from app.services.market import fetch_ohlcv_frame
    from app.services.position_lifecycle import initialize_position_lifecycle, run_position_lifecycle, validate_exit_policy
    from app.services.ml import train_and_score
    from app.services.risk import position_size
    from app.services.risk_engine import RiskGuardrails, build_trade_risk_plan
    from app.services.scanner import select_symbols_for_run
    from app.services.strategies import STRATEGY_MAP, get_strategy_rule

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise RuntimeError(f"user {user_id} not found")
    bot_session = None
    if bot_session_id is not None:
        bot_session = db.query(BotSession).filter(BotSession.id == bot_session_id, BotSession.user_id == user_id).first()
    trade_amount_config = _resolve_trade_amount_config(
        user,
        trade_amount_mode=trade_amount_mode,
        fixed_trade_amount_usd=fixed_trade_amount_usd,
        trade_balance_percent=trade_balance_percent,
    )

    results: list[dict[str, Any]] = []

    for connector_id in connector_ids:
        connector = db.query(Connector).filter(Connector.id == connector_id, Connector.user_id == user_id).first()
        if not connector or not connector.is_enabled:
            results.append({"connector_id": connector_id, "status": "skipped", "reason": "connector_disabled_or_missing"})
            continue
        ensure_connector_market_type_state(connector, persist=True, db=db)
        connector_market_type = resolve_runtime_market_type(connector, requested_market_type=market_type)
        runtime_connector = build_runtime_connector(connector, market_type=connector_market_type)

        client = get_connector_client(runtime_connector)
        lifecycle_meta = run_position_lifecycle(db, connector_ids=[connector.id])
        selected_symbols, scanner_meta = select_symbols_for_run(
            connector_id=connector.id,
            timeframe=timeframe,
            fallback_symbols=symbols,
            cfg=connector.config_json or {},
            connector=connector,
            force_dynamic=str(symbol_source_mode or "manual").lower() == "dynamic",
            max_symbols_override=dynamic_symbol_limit,
        )
        sync_meta = sync_positions_with_exchange(db, runtime_connector, selected_symbols)

        for symbol in selected_symbols:
            decision_reasons: list[str] = []
            market_result = fetch_ohlcv_frame(connector=runtime_connector, symbol=symbol, timeframe=timeframe, limit=220)
            frame = market_result.frame
            notes = {
                "connector": {
                    "id": connector.id,
                    "label": connector.label,
                    "platform": connector.platform,
                    "market_type": connector_market_type,
                    "mode": connector.mode,
                },
                "run_source": run_source,
                "bot_session_id": bot_session_id,
                "bot_session_name": getattr(bot_session, "session_name", None) if bot_session is not None else None,
                "bot_session_display_name": (
                    getattr(bot_session, "session_name", None)
                    or f"{strategy_slug} · {connector.label}"
                ) if bot_session_id is not None else None,
                "scanner": scanner_meta,
                "sync": sync_meta,
                "lifecycle": lifecycle_meta,
                "market_data": market_result.meta,
                "candle": _candle_payload(frame),
                "decision_reasons": decision_reasons,
                "indicator_exit_enabled": indicator_exit_enabled,
                "indicator_exit_rule": indicator_exit_rule,
                "leverage_profile": leverage_profile,
                "compound_growth_enabled": compound_growth_enabled,
                "atr_volatility_filter_enabled": atr_volatility_filter_enabled,
                "symbol_source_mode": symbol_source_mode,
                "dynamic_symbol_limit": dynamic_symbol_limit,
            }
            notes["min_ml_probability"] = min_ml_probability

            market_health = market_result.meta.get("health") or {}
            market_anomalies = market_result.meta.get("anomalies") or {}
            analysis_frame, analysis_meta = _analysis_frame(frame, market_health)
            notes["analysis_frame"] = analysis_meta
            notes["analysis_candle"] = _candle_payload(analysis_frame)
            if frame.empty or analysis_frame.empty:
                decision_reasons.append("missing_market_data")
            notes["market_quality"] = {
                "source": market_result.meta.get("source"),
                "health": market_health,
                "anomalies": market_anomalies,
            }

            strategy_fn = STRATEGY_MAP.get(strategy_slug)
            if strategy_fn is None:
                raise RuntimeError(f"strategy {strategy_slug} not found")

            rule = get_strategy_rule(strategy_slug)
            if connector_market_type not in rule.get("market_types", ["spot", "futures"]):
                decision_reasons.append("strategy_market_mismatch")

            normalized = client.normalize_symbol(symbol)
            notes["symbol_normalization"] = normalized
            normalized_symbol = normalized.get("normalized_symbol") or symbol
            if not normalized.get("found", False) and connector.platform in {"binance", "bybit", "okx"}:
                decision_reasons.append("invalid_symbol")

            execution_environment = client.prepare_execution_environment(
                normalized_symbol,
                leverage_profile=leverage_profile,
            ) if hasattr(client, "prepare_execution_environment") else {"ok": True}
            notes["execution_environment"] = execution_environment
            if not execution_environment.get("ok", True):
                decision_reasons.append("exchange_environment_not_ready")

            if decision_reasons:
                _annotate_decision(notes, decision_reasons, decision="skipped_before_signal")
                run = TradeRun(
                    user_id=user.id,
                    connector_id=connector.id,
                    strategy_slug=strategy_slug,
                    symbol=normalized_symbol,
                    timeframe=timeframe,
                    signal="hold",
                    ml_probability=0.0,
                    quantity=0.0,
                    status=_status_from_reasons(decision_reasons),
                    notes=json.dumps(notes, ensure_ascii=False),
                )
                db.add(run)
                commit_with_retry(db)
                results.append({"connector_id": connector.id, "symbol": normalized_symbol, "status": "skipped", "reasons": decision_reasons})
                continue

            data = analysis_frame
            notes["signal_context"] = _signal_diagnostics(data)
            signal = strategy_fn(data)
            ml_probability = train_and_score(data)
            notes["signal"] = signal
            notes["ml_probability_decimal"] = ml_probability

            if signal == "hold":
                decision_reasons.append("strategy_hold")
            if ml_probability < min_ml_probability:
                decision_reasons.append("low_confidence")

            position_context = client.fetch_position_context(normalized_symbol)
            notes["position_context"] = position_context

            open_positions = db.query(OpenPosition).filter(
                OpenPosition.connector_id == connector.id,
                OpenPosition.is_open.is_(True),
            ).all()
            open_positions = [item for item in open_positions if _safe_float(item.current_qty) > 0]
            open_count = len(open_positions)
            current_open_notional = sum(_safe_float(item.entry_price) * _safe_float(item.current_qty) for item in open_positions)
            current_open_risk = 0.0
            current_symbol_notional = 0.0
            for item in open_positions:
                item_notional = _safe_float(item.entry_price) * _safe_float(item.current_qty)
                if item.symbol == normalized_symbol:
                    current_symbol_notional += item_notional
                stop_price = _safe_float((item.meta_json or {}).get("stop_loss_price"), 0.0)
                if stop_price > 0:
                    current_open_risk += abs(_safe_float(item.entry_price) - stop_price) * _safe_float(item.current_qty)

            if open_count >= max_open_positions and not position_context.get("has_position"):
                decision_reasons.append("max_open_positions")

            if signal == "sell" and connector_market_type != "futures" and not position_context.get("has_position"):
                decision_reasons.append("spot_sell_without_inventory")
            if signal == "sell" and connector_market_type == "futures" and not rule.get("allow_short", False) and not position_context.get("has_position"):
                decision_reasons.append("short_disabled")

            if decision_reasons:
                _annotate_decision(notes, decision_reasons, decision="skipped_signal_validation")
                run = TradeRun(
                    user_id=user.id,
                    connector_id=connector.id,
                    strategy_slug=strategy_slug,
                    symbol=normalized_symbol,
                    timeframe=timeframe,
                    signal=signal,
                    ml_probability=ml_probability,
                    quantity=0.0,
                    status=_status_from_reasons(decision_reasons),
                    notes=json.dumps(notes, ensure_ascii=False),
                )
                db.add(run)
                commit_with_retry(db)
                results.append({"connector_id": connector.id, "symbol": normalized_symbol, "status": "skipped", "reasons": decision_reasons})
                continue

            analysis_price = _safe_float(data.iloc[-1]["close"], 0.0)
            price_context = _resolve_order_price_context(
                client=client,
                symbol=normalized_symbol,
                signal=signal,
                analysis_price=analysis_price,
                market_meta=market_result.meta,
            )
            price = _safe_float(price_context.get("resolved_price"), analysis_price)
            notes["analysis_price"] = analysis_price
            notes["price_context"] = price_context

            balance = client.fetch_available_balance()
            notes["balance"] = balance
            if not balance.get("ok"):
                decision_reasons.append("balance_unavailable")
                _annotate_decision(notes, decision_reasons, decision="skipped_balance")
                run = TradeRun(
                    user_id=user.id,
                    connector_id=connector.id,
                    strategy_slug=strategy_slug,
                    symbol=normalized_symbol,
                    timeframe=timeframe,
                    signal=signal,
                    ml_probability=ml_probability,
                    quantity=0.0,
                    status=_status_from_reasons(decision_reasons),
                    notes=json.dumps(notes, ensure_ascii=False),
                )
                db.add(run)
                commit_with_retry(db)
                results.append({"connector_id": connector.id, "symbol": normalized_symbol, "status": "skipped", "reasons": decision_reasons})
                continue

            stop_loss_price, take_profit_price, stop_pct = _compute_exit_prices(
                signal=signal,
                entry_price=price,
                take_profit_mode=take_profit_mode,
                take_profit_value=take_profit_value,
                stop_loss_mode=stop_loss_mode,
                stop_loss_value=stop_loss_value,
            )

            risk_qty = position_size(_safe_float(balance.get("available_balance"), 0.0), risk_per_trade, price, stop_pct)
            budget_cap_qty = _trade_amount_cap(
                user,
                _safe_float(balance.get("available_balance"), 0.0),
                price,
                trade_amount_mode=str(trade_amount_config["mode"]),
                fixed_trade_amount_usd=_safe_float(trade_amount_config["fixed_trade_amount_usd"], 0.0),
                trade_balance_percent=_safe_float(trade_amount_config["trade_balance_percent"], 0.0),
            )
            quantity = min(risk_qty, budget_cap_qty) if budget_cap_qty > 0 else risk_qty

            guardrails = RiskGuardrails.from_config(
                ((connector.config_json or {}).get("risk_engine") if isinstance(connector.config_json, dict) else {}) or {},
                max_open_positions=max_open_positions,
            )
            risk_plan = build_trade_risk_plan(
                available_balance=_safe_float(balance.get("available_balance"), 0.0),
                price=price,
                stop_loss_price=stop_loss_price,
                requested_qty=quantity,
                risk_per_trade=risk_per_trade,
                current_open_notional=current_open_notional,
                current_open_risk=current_open_risk,
                current_symbol_notional=current_symbol_notional,
                current_open_positions=open_count,
                guardrails=guardrails,
                market_meta=market_result.meta,
            )
            notes["risk_plan"] = risk_plan.to_dict()

            reduce_only = False
            reduce_only_reason = None
            if connector_market_type == "futures" and position_context.get("has_position"):
                current_side = str(position_context.get("side") or "").lower()
                wants_long = signal == "buy"
                wants_short = signal == "sell"
                if (wants_long and current_side == "short") or (wants_short and current_side == "long"):
                    reduce_only = True
                    reduce_only_reason = f"close_{current_side}_before_reentry"

            if connector_market_type != "futures" and signal == "sell":
                quantity = max(
                    _safe_float(position_context.get("spot_base_free"), 0.0),
                    _safe_float(position_context.get("spot_base_total"), 0.0),
                )
            elif reduce_only:
                quantity = max(
                    abs(_safe_float(position_context.get("net_contracts"), 0.0)),
                    current_symbol_notional / max(price, 0.0000001),
                )
            else:
                quantity = risk_plan.approved_qty

            if not risk_plan.approved and signal != "sell":
                decision_reasons.extend(risk_plan.block_reasons or ["risk_engine_blocked"])
            notes["order_preview"] = {
                "price": price,
                "stop_loss_price": stop_loss_price,
                "take_profit_price": take_profit_price,
                "risk_qty": risk_qty,
                "budget_cap_qty": budget_cap_qty,
                "final_quantity": quantity,
                "estimated_notional": quantity * price,
                "estimated_max_loss": quantity * abs(price - stop_loss_price),
                "reduce_only": reduce_only,
                "reduce_only_reason": reduce_only_reason,
                "risk_plan": risk_plan.to_dict(),
            }

            if decision_reasons:
                _annotate_decision(notes, decision_reasons, decision="skipped_risk_validation")
                run = TradeRun(
                    user_id=user.id,
                    connector_id=connector.id,
                    strategy_slug=strategy_slug,
                    symbol=normalized_symbol,
                    timeframe=timeframe,
                    signal=signal,
                    ml_probability=ml_probability,
                    quantity=quantity,
                    status=_status_from_reasons(decision_reasons),
                    notes=json.dumps(notes, ensure_ascii=False),
                )
                db.add(run)
                commit_with_retry(db)
                results.append({"connector_id": connector.id, "symbol": normalized_symbol, "status": "skipped", "reasons": decision_reasons})
                continue

            risk_context = {
                "allow_adjust_up": True,
                "max_qty": max(
                    quantity,
                    _safe_float(balance.get("available_balance"), 0.0) / max(price, 0.0000001),
                ) if signal == "buy" else quantity,
                "max_cost": _safe_float(balance.get("available_balance"), 0.0) if signal == "buy" else (budget_cap_qty * max(price, 0.0000001) if budget_cap_qty > 0 else None),
                "risk_qty": risk_qty,
                "budget_cap_qty": budget_cap_qty,
                "available_balance": _safe_float(balance.get("available_balance"), 0.0),
            }
            connector_context = {
                "connector_id": connector.id,
                "connector_mode": connector.mode,
                "price_guardrails": (connector.config_json or {}).get("price_guardrails") or {},
            }
            pretrade = client.pretrade_validate(
                normalized_symbol,
                quantity,
                price,
                side=signal,
                order_type="market",
                risk_context=risk_context,
                analysis_price=price,
                connector_context=connector_context,
            )
            notes["pretrade"] = pretrade
            if not pretrade.get("ok"):
                decision_reasons.append(pretrade.get("reason_code") or "pretrade_rejected")
                _annotate_decision(notes, decision_reasons, decision="skipped_pretrade")
                run = TradeRun(
                    user_id=user.id,
                    connector_id=connector.id,
                    strategy_slug=strategy_slug,
                    symbol=normalized_symbol,
                    timeframe=timeframe,
                    signal=signal,
                    ml_probability=ml_probability,
                    quantity=quantity,
                    status=_status_from_reasons(decision_reasons),
                    notes=json.dumps(notes, ensure_ascii=False),
                )
                db.add(run)
                commit_with_retry(db)
                send_admin_user_alert_sync(
                    user,
                    format_user_failure_message(
                        locale=user.alert_language,
                        scope="pretrade",
                        detail=pretrade.get("reason_message") or pretrade.get("reason_code") or "pretrade_rejected",
                        connector_label=connector.label,
                        platform=connector.platform,
                        symbol=normalized_symbol,
                    ),
                    scope="pretrade",
                )
                results.append({"connector_id": connector.id, "symbol": normalized_symbol, "status": "skipped", "reasons": decision_reasons})
                continue

            execution_client = client if (use_live_if_available and connector.mode == "live") else BaseConnectorClient(connector)
            try:
                result = execution_client.execute_market(
                    symbol=normalized_symbol,
                    side=signal,
                    quantity=pretrade["normalized_quantity"],
                    price_hint=price,
                    reduce_only=reduce_only,
                )
                notes["execution_raw"] = result.raw
                risk_orders = {}
                if connector_market_type == "futures" and use_live_if_available and connector.mode == "live":
                    risk_orders = client.place_risk_orders(
                        symbol=normalized_symbol,
                        side=signal,
                        quantity=pretrade["normalized_quantity"],
                        stop_loss_price=stop_loss_price,
                        take_profit_price=take_profit_price,
                        trailing_stop_mode=trailing_stop_mode,
                        trailing_stop_value=trailing_stop_value,
                        market_type=connector_market_type,
                    )
                notes["risk_orders"] = risk_orders
            except Exception as exc:
                notes["execution_error"] = str(exc)
                _annotate_decision(notes, ["exchange_rejected"], decision="rejected_exchange")
                run = TradeRun(
                    user_id=user.id,
                    connector_id=connector.id,
                    strategy_slug=strategy_slug,
                    symbol=normalized_symbol,
                    timeframe=timeframe,
                    signal=signal,
                    ml_probability=ml_probability,
                    quantity=pretrade["normalized_quantity"],
                    status="rejected_exchange",
                    notes=json.dumps(notes, ensure_ascii=False),
                )
                db.add(run)
                commit_with_retry(db)
                send_admin_user_alert_sync(
                    user,
                    format_user_failure_message(
                        locale=user.alert_language,
                        scope="execution",
                        detail=str(exc),
                        connector_label=connector.label,
                        platform=connector.platform,
                        symbol=normalized_symbol,
                    ),
                    scope="execution-error",
                )
                results.append({"connector_id": connector.id, "symbol": normalized_symbol, "status": "rejected_exchange", "error": str(exc)})
                continue

            trade_run = TradeRun(
                user_id=user.id,
                connector_id=connector.id,
                strategy_slug=strategy_slug,
                symbol=normalized_symbol,
                timeframe=timeframe,
                signal=signal,
                ml_probability=ml_probability,
                quantity=result.quantity,
                status=result.status,
                notes=json.dumps(notes, ensure_ascii=False),
            )
            db.add(trade_run)
            flush_with_retry(db)

            pnl = 0.0
            close_reason = "entry"
            existing_position = db.query(OpenPosition).filter(
                OpenPosition.connector_id == connector.id,
                OpenPosition.symbol == normalized_symbol,
                OpenPosition.is_open.is_(True),
            ).order_by(OpenPosition.id.desc()).first()

            if reduce_only and existing_position:
                direction = 1 if existing_position.position_side == "long" else -1
                pnl = (result.fill_price - existing_position.entry_price) * result.quantity * direction
                existing_position.current_qty = max(existing_position.current_qty - result.quantity, 0.0)
                existing_position.last_trade_log_id = trade_run.id
                if existing_position.current_qty <= 0:
                    existing_position.is_open = False
                    existing_position.closed_at = __import__("datetime").datetime.utcnow()
                close_reason = reduce_only_reason or "signal_close"
            elif connector_market_type != "futures" and signal == "sell" and existing_position:
                pnl = (result.fill_price - existing_position.entry_price) * result.quantity
                existing_position.is_open = False
                existing_position.current_qty = 0.0
                existing_position.closed_at = __import__("datetime").datetime.utcnow()
                existing_position.last_trade_log_id = trade_run.id
                close_reason = "spot_sell"
            elif existing_position and existing_position.position_side == ("long" if signal == "buy" else "short"):
                prior_qty = max(_safe_float(existing_position.current_qty), 0.0)
                fill_qty = max(_safe_float(result.quantity), 0.0)
                total_qty = prior_qty + fill_qty
                if total_qty > 0:
                    existing_position.entry_price = (
                        (_safe_float(existing_position.entry_price) * prior_qty)
                        + (_safe_float(result.fill_price) * fill_qty)
                    ) / total_qty
                existing_position.current_qty = total_qty
                existing_position.last_trade_log_id = trade_run.id
                existing_position.meta_json = {
                    **(existing_position.meta_json or {}),
                    "last_scale_in_at": __import__("datetime").datetime.utcnow().isoformat(),
                    "last_fill_price": result.fill_price,
                }
                close_reason = "position_scaled_in"
            else:
                new_position = OpenPosition(
                    user_id=user.id,
                    connector_id=connector.id,
                    platform=connector.platform,
                    market_type=connector_market_type,
                    symbol=normalized_symbol,
                    position_side="long" if signal == "buy" else "short",
                    entry_price=result.fill_price,
                    current_qty=result.quantity,
                    source_trade_log_id=trade_run.id,
                    last_trade_log_id=trade_run.id,
                    meta_json={
                        "stop_loss_price": stop_loss_price,
                        "take_profit_price": take_profit_price,
                        "trailing_stop_mode": trailing_stop_mode,
                        "trailing_stop_value": trailing_stop_value,
                        "last_sync": sync_meta.get("synced_at"),
                        "market_data_source": market_result.meta.get("source"),
                    },
                )
                initialize_position_lifecycle(
                    new_position,
                    strategy_slug=strategy_slug,
                    timeframe=timeframe,
                    take_profit_mode=take_profit_mode,
                    take_profit_value=take_profit_value,
                    stop_loss_mode=stop_loss_mode,
                    stop_loss_value=stop_loss_value,
                    trailing_stop_mode=trailing_stop_mode,
                    trailing_stop_value=trailing_stop_value,
                    indicator_exit_enabled=indicator_exit_enabled,
                    indicator_exit_rule=indicator_exit_rule,
                    bot_session_id=bot_session_id,
                    run_source=run_source,
                )
                policy_ok, policy_errors = validate_exit_policy((new_position.meta_json or {}).get("exit_policy") or {})
                if not policy_ok:
                    raise RuntimeError(f"critical_missing_exit_policy:{','.join(policy_errors)}")
                db.add(new_position)

            _annotate_decision(notes, [], decision="executed")
            trade_run.notes = json.dumps(notes, ensure_ascii=False)

            db.add(TradeLog(
                user_id=user.id,
                connector_id=connector.id,
                platform=connector.platform,
                symbol=normalized_symbol,
                side=signal,
                quantity=result.quantity,
                price=result.fill_price,
                status=result.status,
                pnl=pnl,
                meta_json={
                    "stop_loss_price": stop_loss_price,
                    "take_profit_price": take_profit_price,
                    "close_reason": close_reason,
                    "capital_allocated": round(
                        min(
                            _safe_float(balance.get("available_balance"), 0.0),
                            _safe_float(trade_amount_config["fixed_trade_amount_usd"], 10.0)
                            if str(trade_amount_config["mode"]).lower() == "fixed_usd"
                            else (_safe_float(balance.get("available_balance"), 0.0) * (_safe_float(trade_amount_config["trade_balance_percent"], 10.0) / 100.0)),
                        ),
                        8,
                    ),
                    "trade_amount_mode": trade_amount_config["mode"],
                    "trade_amount_fixed_usd": trade_amount_config["fixed_trade_amount_usd"],
                    "trade_amount_percent": trade_amount_config["trade_balance_percent"],
                    "market_data": market_result.meta,
                    "pretrade": pretrade,
                    "balance": balance,
                    "execution_raw": result.raw,
                    "risk_plan": risk_plan.to_dict(),
                },
            ))
            commit_with_retry(db)

            send_admin_user_alert_sync(
                user,
                format_user_execution_message(
                    locale=user.alert_language,
                    connector_label=connector.label,
                    platform=connector.platform,
                    symbol=normalized_symbol,
                    side=signal,
                    quantity=result.quantity,
                    fill_price=result.fill_price,
                    status=result.status,
                    strategy_slug=strategy_slug,
                    message=result.message,
                    pnl=pnl,
                    close_reason=close_reason,
                ),
                scope="execution-ok",
            )
            results.append({
                "connector_id": connector.id,
                "symbol": normalized_symbol,
                "status": result.status,
                "quantity": result.quantity,
                "fill_price": result.fill_price,
                "market_data_source": market_result.meta.get("source"),
                "balance_source": balance.get("source"),
            })

    return results


def dashboard_data(db, user_id: int) -> dict[str, Any]:
    from app.models import Connector, TradeLog
    from app.services.risk_engine import summarize_portfolio_risk

    connectors = db.query(Connector).filter(Connector.user_id == user_id).all()
    trades = db.query(TradeLog).filter(TradeLog.user_id == user_id).order_by(TradeLog.created_at.desc()).all()
    latest_trades = trades[:20]

    realized_pnl = sum(_safe_float(item.pnl) for item in trades)
    total_invested = sum(
        _safe_float((item.meta_json or {}).get("capital_allocated"))
        or (_safe_float(item.quantity) * _safe_float(item.price))
        for item in trades
    )
    winning_trades = sum(1 for item in trades if _safe_float(item.pnl) > 0)
    losing_trades = sum(1 for item in trades if _safe_float(item.pnl) < 0)
    platforms: dict[str, dict[str, Any]] = {}
    statuses: dict[str, int] = {}

    for trade in trades:
        bucket = platforms.setdefault(trade.platform or "unknown", {"count": 0, "pnl": 0.0})
        bucket["count"] += 1
        bucket["pnl"] += _safe_float(trade.pnl)
        statuses[trade.status or "unknown"] = statuses.get(trade.status or "unknown", 0) + 1

    risk_summary = summarize_portfolio_risk(db, user_id)
    return {
        "total_connectors": len(connectors),
        "enabled_connectors": sum(1 for item in connectors if item.is_enabled),
        "total_trades": len(trades),
        "realized_pnl": round(realized_pnl, 6),
        "total_invested": round(total_invested, 6),
        "realized_pnl_percent": round((realized_pnl / total_invested) * 100.0, 6) if total_invested > 0 else 0.0,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "platforms": platforms,
        "statuses": statuses,
        "latest_trades": latest_trades,
        "limits": [],
        "risk_summary": risk_summary,
        "insights": risk_summary.get("suggestions", []),
    }


def activity_metrics(db, user_id: int) -> dict[str, Any]:
    from collections import defaultdict

    from app.models import TradeLog

    trades = db.query(TradeLog).filter(TradeLog.user_id == user_id).order_by(TradeLog.created_at.asc()).all()

    equity_curve = []
    drawdown_curve = []
    monthly_returns = defaultdict(float)
    yearly_returns = defaultdict(float)
    running = 0.0
    peak = 0.0
    pnl_values = []

    for trade in trades:
        pnl = _safe_float(trade.pnl)
        pnl_values.append(pnl)
        running += pnl
        peak = max(peak, running)
        drawdown = running - peak
        stamp = trade.created_at.isoformat() if trade.created_at else None
        equity_curve.append({"timestamp": stamp, "value": round(running, 6)})
        drawdown_curve.append({"timestamp": stamp, "value": round(drawdown, 6)})
        if trade.created_at:
            monthly_returns[trade.created_at.strftime("%Y-%m")] += pnl
            yearly_returns[trade.created_at.strftime("%Y")] += pnl

    avg_win = sum(x for x in pnl_values if x > 0) / max(sum(1 for x in pnl_values if x > 0), 1)
    avg_loss = abs(sum(x for x in pnl_values if x < 0) / max(sum(1 for x in pnl_values if x < 0), 1))
    profit_factor = (sum(x for x in pnl_values if x > 0) / max(abs(sum(x for x in pnl_values if x < 0)), 0.0000001)) if pnl_values else 0.0
    win_rate = (sum(1 for x in pnl_values if x > 0) / len(pnl_values) * 100.0) if pnl_values else 0.0
    mean = sum(pnl_values) / len(pnl_values) if pnl_values else 0.0
    variance = sum((x - mean) ** 2 for x in pnl_values) / len(pnl_values) if pnl_values else 0.0
    std = variance ** 0.5
    sharpe_ratio = mean / std if std > 0 else 0.0

    return {
        "equity_curve": equity_curve,
        "drawdown_curve": drawdown_curve,
        "monthly_returns": [{"period": key, "value": round(value, 6)} for key, value in sorted(monthly_returns.items())],
        "yearly_returns": [{"period": key, "value": round(value, 6)} for key, value in sorted(yearly_returns.items())],
        "summary": {
            "sharpe_ratio": round(sharpe_ratio, 6),
            "max_drawdown": round(min((item["value"] for item in drawdown_curve), default=0.0), 6),
            "profit_factor": round(profit_factor, 6),
            "win_rate": round(win_rate, 6),
            "total_trades": len(trades),
            "average_win": round(avg_win, 6),
            "average_loss": round(avg_loss, 6),
        },
    }
