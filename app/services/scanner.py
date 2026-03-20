from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.services.indicators import add_indicators
from app.services.market import fetch_ohlcv_frame, synthetic_ohlcv

_SCANNER_CACHE: dict[str, dict[str, Any]] = {}


def _score_symbol(symbol: str, timeframe: str, connector=None) -> dict[str, Any] | None:
    if connector is not None:
        market_result = fetch_ohlcv_frame(connector=connector, symbol=symbol, timeframe=timeframe, limit=180)
        df_raw = market_result.frame
        data_source = market_result.meta.get("source")
    else:
        df_raw = synthetic_ohlcv(symbol=symbol, timeframe=timeframe)
        data_source = "synthetic_fallback"
    df = add_indicators(df_raw)
    if df.empty:
        return None

    row = df.iloc[-1]

    adx = float(row.get("adx", 0) or 0)
    ret_1 = float(row.get("ret_1", 0) or 0)
    ret_5 = float(row.get("ret_5", 0) or 0)
    vol_10 = float(row.get("vol_10", 0) or 0)
    volume = float(row.get("volume", 0) or 0)
    ema_fast = float(row.get("ema_fast", 0) or 0)
    ema_slow = float(row.get("ema_slow", 0) or 0)
    close = float(row.get("close", 0) or 0)

    trend_bonus = 1.0 if ema_fast > ema_slow else -0.5
    momentum_component = (ret_1 * 100.0) + (ret_5 * 80.0)
    volatility_component = vol_10 * 120.0
    adx_component = adx * 0.6
    liquidity_component = min(volume / 100000.0, 5.0)
    price_component = 0.3 if close > 0 else -2.0
    stretch_threshold = max(0.04, vol_10 * 2.0)
    stretch_excess = max(abs(ret_5) - stretch_threshold, 0.0)
    stretch_penalty = stretch_excess * 800.0

    score = trend_bonus + momentum_component + volatility_component + adx_component + liquidity_component + price_component - stretch_penalty

    return {
        "symbol": symbol,
        "score": round(float(score), 6),
        "close": round(close, 8),
        "adx": round(adx, 4),
        "ret_1": round(ret_1, 6),
        "ret_5": round(ret_5, 6),
        "vol_10": round(vol_10, 6),
        "volume": round(volume, 4),
        "trend_up": ema_fast > ema_slow,
        "stretch_threshold": round(stretch_threshold, 6),
        "stretch_excess": round(stretch_excess, 6),
        "stretch_penalty": round(stretch_penalty, 6),
        "data_source": data_source,
    }


def _normalize_universe(cfg: dict, fallback_symbols: list[str]) -> list[str]:
    configured = cfg.get("scanner_universe") or cfg.get("smart_scanner_universe") or []
    if isinstance(configured, str):
        configured = [x.strip() for x in configured.split(",") if x.strip()]
    if not configured:
        configured = list(fallback_symbols)

    if not configured:
        configured = [
            "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT",
            "XRP/USDT", "ADA/USDT", "DOGE/USDT", "AVAX/USDT",
            "LINK/USDT", "MATIC/USDT", "AR/USDT", "INJ/USDT",
            "OP/USDT", "APT/USDT", "SUI/USDT", "SEI/USDT",
            "RUNE/USDT", "FTM/USDT", "NEAR/USDT", "ATOM/USDT",
            "PEPE/USDT", "WIF/USDT", "BONK/USDT"
        ]

    seen = set()
    final = []
    for item in configured:
        sym = str(item).strip()
        if sym and sym not in seen:
            seen.add(sym)
            final.append(sym)
    return final


def select_symbols_for_run(
    connector_id: int,
    timeframe: str,
    fallback_symbols: list[str],
    cfg: dict,
    connector=None,
    *,
    force_dynamic: bool = False,
    max_symbols_override: int | None = None,
) -> tuple[list[str], dict[str, Any]]:
    auto_scan_enabled = bool(cfg.get("auto_scan_enabled", False)) or force_dynamic
    max_symbols = max(int(max_symbols_override or cfg.get("max_symbols", 10) or 10), 1)
    scanner_interval_minutes = int(cfg.get("scanner_interval_minutes", 60) or 60)

    if not auto_scan_enabled:
        selected = list(fallback_symbols)[:max_symbols]
        return selected, {
            "mode": "manual",
            "reason": "auto_scan_disabled",
            "selected_symbols": selected,
            "selected_count": len(selected),
            "max_symbols": max_symbols,
            "timeframe": timeframe,
        }

    universe = _normalize_universe(cfg, fallback_symbols)
    if not universe:
        return list(fallback_symbols), {
            "mode": "manual",
            "reason": "empty_universe_fallback",
            "selected_symbols": list(fallback_symbols),
            "selected_count": len(list(fallback_symbols)),
            "max_symbols": max_symbols,
            "timeframe": timeframe,
        }

    cache_key = f"{connector_id}:{timeframe}"
    now = datetime.utcnow()
    cached = _SCANNER_CACHE.get(cache_key)

    if cached:
        scanned_at = cached.get("scanned_at")
        if isinstance(scanned_at, datetime) and now - scanned_at < timedelta(minutes=scanner_interval_minutes):
            return list(cached.get("symbols", fallback_symbols)), {
                "mode": "auto",
                "cached": True,
                "scanned_at": scanned_at.isoformat(),
                "selected_symbols": list(cached.get("symbols", fallback_symbols)),
                "selected_count": len(list(cached.get("symbols", fallback_symbols))),
                "max_symbols": max_symbols,
                "ranking": cached.get("ranking", []),
                "timeframe": timeframe,
            }

    ranking = []
    for symbol in universe:
        scored = _score_symbol(symbol, timeframe, connector=connector)
        if scored:
            ranking.append(scored)

    ranking.sort(key=lambda x: x["score"], reverse=True)
    selected = [item["symbol"] for item in ranking[:max_symbols]]

    if not selected:
        selected = list(fallback_symbols)[:max_symbols]

    _SCANNER_CACHE[cache_key] = {
        "scanned_at": now,
        "symbols": selected,
        "ranking": ranking[: max(max_symbols, 20)],
    }

    return selected, {
        "mode": "auto",
        "cached": False,
        "scanned_at": now.isoformat(),
        "selected_symbols": selected,
        "selected_count": len(selected),
        "max_symbols": max_symbols,
        "ranking": ranking[: max(max_symbols, 20)],
        "timeframe": timeframe,
    }
