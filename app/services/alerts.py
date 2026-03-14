from __future__ import annotations

from datetime import datetime, timezone
import logging

import httpx

from app.core import settings
from app.models import User
from app.security import decrypt_payload

logger = logging.getLogger(__name__)
SUPPORTED_ALERT_LOCALES = {"es", "en", "pt", "fr"}


def normalize_alert_locale(value: str | None) -> str:
    locale = (value or "es").strip().lower()
    if locale not in SUPPORTED_ALERT_LOCALES:
        return "es"
    return locale


def _safe_telegram_text(message: str) -> str:
    return message[:3900]


def _compose_telegram_url(token: str) -> str:
    return f"https://api.telegram.org/bot{token}/sendMessage"


async def send_telegram_alert(message: str) -> bool:
    token = (settings.telegram_admin_bot_token or "").strip()
    chat_id = (settings.telegram_admin_chat_id or "").strip()
    if not token or not chat_id:
        return False

    payload = {
        "chat_id": chat_id,
        "text": _safe_telegram_text(message),
        "disable_web_page_preview": True,
    }
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            response = await client.post(_compose_telegram_url(token), json=payload)
            response.raise_for_status()
        return True
    except Exception:
        logger.exception("Failed sending Telegram alert")
        return False


def send_telegram_alert_sync(message: str) -> bool:
    token = (settings.telegram_admin_bot_token or "").strip()
    chat_id = (settings.telegram_admin_chat_id or "").strip()
    if not token or not chat_id:
        return False

    payload = {
        "chat_id": chat_id,
        "text": _safe_telegram_text(message),
        "disable_web_page_preview": True,
    }
    try:
        with httpx.Client(timeout=6.0) as client:
            response = client.post(_compose_telegram_url(token), json=payload)
            response.raise_for_status()
        return True
    except Exception:
        logger.exception("Failed sending sync Telegram alert")
        return False


def send_user_telegram_alert(user: User, message: str) -> bool:
    if not user.telegram_alerts_enabled:
        return False

    token = (decrypt_payload(user.telegram_bot_token_encrypted).get("value") or "").strip()
    chat_id = (decrypt_payload(user.telegram_chat_id_encrypted).get("value") or "").strip()
    if not token or not chat_id:
        return False

    payload = {
        "chat_id": chat_id,
        "text": _safe_telegram_text(message),
        "disable_web_page_preview": True,
    }
    try:
        with httpx.Client(timeout=6.0) as client:
            response = client.post(_compose_telegram_url(token), json=payload)
            response.raise_for_status()
        return True
    except Exception:
        logger.exception("Failed sending user Telegram alert for user_id=%s", user.id)
        return False


def format_failure_message(scope: str, detail: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return (
        "🚨 TradingSaas Failure Alert\n"
        f"Time: {now}\n"
        f"Scope: {scope}\n"
        f"Detail: {detail}"
    )


def format_user_execution_message(*, locale: str, connector_label: str, platform: str, symbol: str,
                                  side: str, quantity: float, fill_price: float, status: str,
                                  strategy_slug: str, message: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    locale = normalize_alert_locale(locale)
    if locale == "en":
        return (
            "✅ Trade executed\n"
            f"Time: {now}\n"
            f"Connector: {connector_label} ({platform})\n"
            f"Pair: {symbol}\n"
            f"Action: {side.upper()}\n"
            f"Quantity: {quantity:.8f}\n"
            f"Price: {fill_price:.8f}\n"
            f"Status: {status}\n"
            f"Strategy: {strategy_slug}\n"
            f"Details: {message}"
        )
    if locale == "pt":
        return (
            "✅ Operação executada\n"
            f"Horário: {now}\n"
            f"Conector: {connector_label} ({platform})\n"
            f"Par: {symbol}\n"
            f"Ação: {side.upper()}\n"
            f"Quantidade: {quantity:.8f}\n"
            f"Preço: {fill_price:.8f}\n"
            f"Status: {status}\n"
            f"Estratégia: {strategy_slug}\n"
            f"Detalhes: {message}"
        )
    if locale == "fr":
        return (
            "✅ Ordre exécuté\n"
            f"Heure: {now}\n"
            f"Connecteur: {connector_label} ({platform})\n"
            f"Pair: {symbol}\n"
            f"Action: {side.upper()}\n"
            f"Quantité: {quantity:.8f}\n"
            f"Prix: {fill_price:.8f}\n"
            f"Statut: {status}\n"
            f"Stratégie: {strategy_slug}\n"
            f"Détails: {message}"
        )
    return (
        "✅ Operación ejecutada\n"
        f"Hora: {now}\n"
        f"Conector: {connector_label} ({platform})\n"
        f"Par: {symbol}\n"
        f"Acción: {side.upper()}\n"
        f"Cantidad: {quantity:.8f}\n"
        f"Precio: {fill_price:.8f}\n"
        f"Estado: {status}\n"
        f"Estrategia: {strategy_slug}\n"
        f"Detalle: {message}"
    )


def format_user_failure_message(*, locale: str, scope: str, detail: str, connector_label: str | None = None,
                                platform: str | None = None, symbol: str | None = None) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    locale = normalize_alert_locale(locale)
    where = f"{connector_label} ({platform})" if connector_label and platform else "-"
    pair = symbol or "-"

    if locale == "en":
        return (
            "🚨 Account error detected\n"
            f"Time: {now}\n"
            f"Scope: {scope}\n"
            f"Connector: {where}\n"
            f"Pair: {pair}\n"
            f"Details: {detail}"
        )
    if locale == "pt":
        return (
            "🚨 Falha detectada na conta\n"
            f"Horário: {now}\n"
            f"Escopo: {scope}\n"
            f"Conector: {where}\n"
            f"Par: {pair}\n"
            f"Detalhes: {detail}"
        )
    if locale == "fr":
        return (
            "🚨 Erreur détectée sur le compte\n"
            f"Heure: {now}\n"
            f"Portée: {scope}\n"
            f"Connecteur: {where}\n"
            f"Pair: {pair}\n"
            f"Détails: {detail}"
        )
    return (
        "🚨 Falla detectada en la cuenta\n"
        f"Hora: {now}\n"
        f"Ámbito: {scope}\n"
        f"Conector: {where}\n"
        f"Par: {pair}\n"
        f"Detalle: {detail}"
    )
