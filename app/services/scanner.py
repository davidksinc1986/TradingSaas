from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.services.indicators import add_indicators
from app.services.market import synthetic_ohlcv

_SCANNER_CACHE: dict[str, dict[str, Any]] = {}


def _score_symbol(symbol: str, timeframe: str) -> dict[str, Any] | None:
    df_raw = synthetic_ohlcv(symbol=symbol, timeframe=timeframe)
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

    score = trend_bonus + momentum_component + volatility_component + adx_component + liquidity_component + price_component

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
    }


def _normalize_universe(cfg: dict, fallback_symbols: list[str]) -> list[str]:
    configured = cfg.get("scanner_universe") or cfg.get("smart_scanner_universe") or []
    if isinstance(configured, str):
        configured = [x.strip() for x in configured.split(",") if x.strip()]
    if not configured:
        configured = list(fallback_symbols)
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
) -> tuple[list[str], dict[str, Any]]:
    smart_scanner_enabled = bool(cfg.get("smart_scanner_enabled", False))
    scanner_top_n = int(cfg.get("scanner_top_n", cfg.get("smart_select_top_n", 0) or 0))
    scanner_interval_minutes = int(cfg.get("scanner_interval_minutes", 60) or 60)

    if not smart_scanner_enabled:
        return list(fallback_symbols), {
            "enabled": False,
            "reason": "smart_scanner_disabled",
            "selected_symbols": list(fallback_symbols),
        }

    universe = _normalize_universe(cfg, fallback_symbols)
    if not universe:
        return list(fallback_symbols), {
            "enabled": True,
            "reason": "scanner_empty_universe_fallback",
            "selected_symbols": list(fallback_symbols),
        }

    if scanner_top_n <= 0:
        scanner_top_n = min(len(universe), 10)

    cache_key = f"{connector_id}:{timeframe}"
    now = datetime.utcnow()
    cached = _SCANNER_CACHE.get(cache_key)

    if cached:
        scanned_at = cached.get("scanned_at")
        if isinstance(scanned_at, datetime) and now - scanned_at < timedelta(minutes=scanner_interval_minutes):
            return list(cached.get("symbols", fallback_symbols)), {
                "enabled": True,
                "cached": True,
                "scanned_at": scanned_at.isoformat(),
                "selected_symbols": list(cached.get("symbols", fallback_symbols)),
                "ranking": cached.get("ranking", []),
                "universe_size": len(universe),
                "interval_minutes": scanner_interval_minutes,
            }

    ranking = []
    for symbol in universe:
        scored = _score_symbol(symbol, timeframe)
        if scored:
            ranking.append(scored)

    ranking.sort(key=lambda x: x["score"], reverse=True)
    selected_symbols = [item["symbol"] for item in ranking[:scanner_top_n]] or list(fallback_symbols)

    _SCANNER_CACHE[cache_key] = {
        "scanned_at": now,
        "symbols": selected_symbols,
        "ranking": ranking[: max(scanner_top_n, 20)],
    }

    return selected_symbols, {
        "enabled": True,
        "cached": False,
        "scanned_at": now.isoformat(),
        "selected_symbols": selected_symbols,
        "ranking": ranking[: max(scanner_top_n, 20)],
        "universe_size": len(universe),
        "interval_minutes": scanner_interval_minutes,
    }
