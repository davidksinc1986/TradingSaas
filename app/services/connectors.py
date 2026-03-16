from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.security import decrypt_payload

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

    def execute_market(self, symbol: str, side: str, quantity: float, price_hint: float) -> ExecutionResult:
        return ExecutionResult(
            status="paper-filled",
            message="Paper execution completed",
            fill_price=price_hint,
            quantity=quantity,
            raw={"mode": self.connector.mode, "platform": self.connector.platform, "market_type": getattr(self.connector, "market_type", "spot")},
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
        return {"ok": True, "platform": self.connector.platform, "mode": self.connector.mode, "market_type": getattr(self.connector, "market_type", "spot")}


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

    def _resolve_fill_price(self, order: dict[str, Any], price_hint: float) -> float:
        return float(order.get("average") or order.get("price") or order.get("cost") or price_hint)

    def execute_market(self, symbol: str, side: str, quantity: float, price_hint: float) -> ExecutionResult:
        if self.connector.mode != "live":
            return super().execute_market(symbol, side, quantity, price_hint)
        exchange = self.build_exchange()
        quantity, normalized_price, min_notional = self._apply_exchange_filters(exchange, symbol, quantity, price_hint)
        if quantity <= 0:
            raise RuntimeError(f"Quantity for {symbol} resolved to 0 after exchange precision filters")
        order = exchange.create_order(symbol=symbol, type="market", side=side, amount=quantity)
        fill_price = self._resolve_fill_price(order, price_hint)
        return ExecutionResult(
            status="live-submitted",
            message="Live order submitted via CCXT",
            fill_price=fill_price,
            quantity=float(order.get("amount") or quantity),
            raw={**order, "normalized_price": normalized_price, "min_notional": min_notional},
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

    def execute_market(self, symbol: str, side: str, quantity: float, price_hint: float) -> ExecutionResult:
        if self.connector.mode != "live":
            return super().execute_market(symbol, side, quantity, price_hint)
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
                raw=result_dict,
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

    def execute_market(self, symbol: str, side: str, quantity: float, price_hint: float) -> ExecutionResult:
        if self.connector.mode != "live":
            return super().execute_market(symbol, side, quantity, price_hint)
        bridge_url = self._bridge_url()
        if not bridge_url:
            return ExecutionResult(
                status="bridge-required",
                message="cTrader live mode requires a bridge_url or a dedicated Open API client implementation.",
                fill_price=price_hint,
                quantity=quantity,
                raw={"platform": "ctrader"},
            )
        payload = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price_hint": price_hint,
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
