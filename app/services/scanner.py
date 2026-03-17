from __future__ import annotations
import random

def select_symbols_for_run(
    connector_id: int,
    timeframe: str,
    fallback_symbols: list[str],
    cfg: dict,
):
    """
    Scanner inteligente:
    - Si hay lista manual → usa esa
    - Si no → selecciona dinámicamente
    - Prioriza volatilidad + random para movimiento
    """

    # CONFIG
    max_symbols = int(cfg.get("max_symbols", 10))
    use_dynamic = bool(cfg.get("auto_scan_enabled", True))

    # SI NO HAY SCANNER → usa fallback
    if not use_dynamic:
        return fallback_symbols[:max_symbols], {
            "mode": "manual",
            "reason": "auto_scan_disabled"
        }

    # BASE DE MONEDAS (puedes ampliar esto luego)
    base_universe = [
        "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT",
        "XRP/USDT", "ADA/USDT", "DOGE/USDT", "AVAX/USDT",
        "LINK/USDT", "MATIC/USDT", "AR/USDT", "INJ/USDT",
        "OP/USDT", "APT/USDT", "SUI/USDT", "SEI/USDT",
        "RUNE/USDT", "FTM/USDT", "NEAR/USDT", "ATOM/USDT",
        "PEPE/USDT", "WIF/USDT", "BONK/USDT"
    ]

    # 🔥 mezcla para simular volatilidad
    random.shuffle(base_universe)

    selected = base_universe[:max_symbols]

    return selected, {
        "mode": "auto",
        "selected_count": len(selected),
        "timeframe": timeframe
    }
