from __future__ import annotations

from typing import Any


PLATFORM_MARKET_TYPES = {
    "mt5": {"forex", "cfd"},
    "ctrader": {"forex", "cfd", "spot", "futures"},
    "tradingview": {"signals"},
    "binance": {"spot", "futures"},
    "bybit": {"spot", "futures"},
    "okx": {"spot", "futures"},
}


def normalize_market_type(value: str | None) -> str:
    clean = str(value or "").strip().lower()
    aliases = {
        "future": "futures",
        "futures": "futures",
        "perpetual": "futures",
        "swap": "futures",
        "signal": "signals",
        "signals": "signals",
    }
    return aliases.get(clean, clean or "spot")


def resolve_connector_market_type(*, platform: str, market_type: str | None = None, config: dict[str, Any] | None = None) -> str:
    cfg = config or {}
    resolved = normalize_market_type(
        market_type
        or cfg.get("market_type")
        or cfg.get("defaultType")
        or cfg.get("default_type")
    )
    allowed = PLATFORM_MARKET_TYPES.get(str(platform or "").lower(), {"spot"})
    if resolved in allowed:
        return resolved
    if resolved == "spot" and "spot" not in allowed:
        return sorted(allowed)[0]
    raise ValueError(
        f"El mercado {resolved} no es válido para {platform}. Permitidos: {', '.join(sorted(allowed))}"
    )


def sync_connector_config_market_type(config: dict[str, Any] | None, market_type: str) -> dict[str, Any]:
    current = dict(config or {})
    current["market_type"] = market_type
    if market_type in {"spot", "futures"}:
        current["defaultType"] = "future" if market_type == "futures" else "spot"
    return current


def ensure_connector_market_type_state(connector, *, persist: bool = False, db=None) -> str:
    resolved = resolve_connector_market_type(
        platform=str(getattr(connector, "platform", "") or ""),
        market_type=getattr(connector, "market_type", None),
        config=getattr(connector, "config_json", None),
    )
    next_config = sync_connector_config_market_type(getattr(connector, "config_json", None), resolved)
    changed = False
    if getattr(connector, "market_type", None) != resolved:
        connector.market_type = resolved
        changed = True
    if getattr(connector, "config_json", None) != next_config:
        connector.config_json = next_config
        changed = True
    if persist and changed and db is not None:
        db.add(connector)
    return resolved
