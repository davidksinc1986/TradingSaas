from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from random import gauss, random
from typing import Any

import pandas as pd


@dataclass
class MarketFrameResult:
    frame: pd.DataFrame
    meta: dict[str, Any]


def synthetic_ohlcv(symbol: str, periods: int = 300, timeframe: str = "1h") -> pd.DataFrame:
    seed_bias = (sum(ord(c) for c in symbol) % 17) / 1000
    drift = 0.0005 + seed_bias
    vol = 0.015 + ((sum(ord(c) for c in symbol) % 7) / 1000)
    end = datetime.utcnow()
    step = _timeframe_delta(timeframe)
    timestamps = [end - step * i for i in range(periods)][::-1]
    prices = [100.0 + (sum(ord(c) for c in symbol) % 50)]
    for _ in range(1, periods):
        shock = gauss(drift, vol)
        prices.append(max(1.0, prices[-1] * (1 + shock)))
    rows = []
    for ts, close in zip(timestamps, prices):
        high = close * (1 + abs(random()) * 0.01)
        low = close * (1 - abs(random()) * 0.01)
        open_ = close * (1 + gauss(0, 0.003))
        volume = abs(gauss(1000, 250))
        rows.append({"timestamp": ts, "open": open_, "high": high, "low": low, "close": close, "volume": volume})
    return pd.DataFrame(rows)


def _timeframe_delta(timeframe: str) -> timedelta:
    clean = str(timeframe or "1h").strip().lower()
    if clean.endswith("m"):
        return timedelta(minutes=max(int(clean[:-1] or 1), 1))
    if clean.endswith("h"):
        return timedelta(hours=max(int(clean[:-1] or 1), 1))
    if clean.endswith("d"):
        return timedelta(days=max(int(clean[:-1] or 1), 1))
    return timedelta(hours=1)


def _normalize_ohlcv_frame(raw_rows: list[list[Any]] | None) -> pd.DataFrame:
    rows = raw_rows or []
    frame = pd.DataFrame(rows, columns=["timestamp_ms", "open", "high", "low", "close", "volume"])
    if frame.empty:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

    frame["timestamp"] = pd.to_datetime(frame["timestamp_ms"], unit="ms", utc=True).dt.tz_convert(None)
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["timestamp", "open", "high", "low", "close"]).reset_index(drop=True)
    return frame[["timestamp", "open", "high", "low", "close", "volume"]]


def _market_data_health(frame: pd.DataFrame, timeframe: str) -> dict[str, Any]:
    if frame.empty:
        return {
            "status": "error",
            "has_unconfirmed_candle": None,
            "latency_seconds": None,
            "close_timestamp": None,
            "issues": ["empty_frame"],
        }

    close_timestamp = frame.iloc[-1]["timestamp"]
    if hasattr(close_timestamp, "to_pydatetime"):
        close_timestamp = close_timestamp.to_pydatetime()

    now = datetime.utcnow()
    delta = _timeframe_delta(timeframe)
    latency_seconds = max((now - close_timestamp).total_seconds(), 0.0)
    has_unconfirmed = latency_seconds < delta.total_seconds()
    issues = []
    if has_unconfirmed:
        issues.append("last_candle_not_closed")
    if latency_seconds > delta.total_seconds() * 3:
        issues.append("stale_feed")

    return {
        "status": "warning" if issues else "ok",
        "has_unconfirmed_candle": has_unconfirmed,
        "latency_seconds": round(latency_seconds, 3),
        "close_timestamp": close_timestamp.isoformat(),
        "issues": issues,
    }


def fetch_ohlcv_frame(connector, symbol: str, timeframe: str = "1h", limit: int = 300) -> MarketFrameResult:
    from app.services.connectors import CCXTConnectorClient, get_client

    client = get_client(connector)
    normalized_symbol = symbol
    source = "synthetic_fallback"
    notes: list[str] = []

    try:
        symbol_meta = client.normalize_symbol(symbol)
        normalized_symbol = symbol_meta.get("normalized_symbol") or symbol
    except Exception as exc:
        symbol_meta = {"input_symbol": symbol, "normalized_symbol": symbol, "found": False, "error": str(exc)}
        notes.append(f"normalize_symbol_failed:{exc}")

    if connector.mode == "live" and isinstance(client, CCXTConnectorClient):
        try:
            exchange = client.build_exchange()
            raw_rows = exchange.fetch_ohlcv(normalized_symbol, timeframe=timeframe, limit=limit)
            frame = _normalize_ohlcv_frame(raw_rows)
            if not frame.empty:
                ticker = exchange.fetch_ticker(normalized_symbol)
                last_price = float(ticker.get("last") or ticker.get("close") or frame.iloc[-1]["close"])
                bot_price = float(frame.iloc[-1]["close"])
                difference_pct = abs(bot_price - last_price) / max(last_price, 0.0000001) * 100.0
                return MarketFrameResult(
                    frame=frame,
                    meta={
                        "source": "exchange_ohlcv",
                        "symbol": normalized_symbol,
                        "symbol_meta": symbol_meta,
                        "exchange_price": last_price,
                        "bot_price": bot_price,
                        "difference_pct": round(difference_pct, 6),
                        "health": _market_data_health(frame, timeframe),
                        "notes": notes,
                    },
                )
            notes.append("empty_exchange_ohlcv")
        except Exception as exc:
            notes.append(f"exchange_ohlcv_failed:{exc}")

    frame = synthetic_ohlcv(symbol=normalized_symbol, periods=limit, timeframe=timeframe)
    return MarketFrameResult(
        frame=frame,
        meta={
            "source": source,
            "symbol": normalized_symbol,
            "symbol_meta": symbol_meta,
            "exchange_price": None,
            "bot_price": float(frame.iloc[-1]["close"]) if not frame.empty else None,
            "difference_pct": None,
            "health": _market_data_health(frame, timeframe),
            "notes": notes or ["using_synthetic_data"],
        },
    )


def price_check(connector, symbol: str, timeframe: str = "1h") -> dict[str, Any]:
    result = fetch_ohlcv_frame(connector=connector, symbol=symbol, timeframe=timeframe, limit=120)
    frame = result.frame
    meta = result.meta
    return {
        "symbol": meta.get("symbol") or symbol,
        "timeframe": timeframe,
        "data_source": meta.get("source"),
        "bot_price": float(meta.get("bot_price") or 0.0),
        "exchange_price": float(meta.get("exchange_price") or 0.0) if meta.get("exchange_price") is not None else None,
        "difference_pct": meta.get("difference_pct"),
        "health": meta.get("health") or {},
        "last_candle_timestamp": frame.iloc[-1]["timestamp"].isoformat() if not frame.empty else None,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "notes": meta.get("notes") or [],
    }
