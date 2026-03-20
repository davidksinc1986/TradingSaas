from __future__ import annotations

from datetime import datetime, timezone
import logging

import httpx

from app.core import settings
from app.models import User
from app.security import decrypt_payload

logger = logging.getLogger(__name__)
SUPPORTED_ALERT_LOCALES = {"es", "en", "pt", "fr"}


class TelegramDeliveryError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, description: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.description = description or message


def normalize_alert_locale(value: str | None) -> str:
    locale = (value or "es").strip().lower()
    if locale not in SUPPORTED_ALERT_LOCALES:
        return "es"
    return locale


def _safe_telegram_text(message: str) -> str:
    return message[:3900]


def _compose_telegram_url(token: str) -> str:
    return f"https://api.telegram.org/bot{token}/sendMessage"


def _build_telegram_error(status_code: int | None, description: str) -> TelegramDeliveryError:
    detail = (description or "").strip()
    lowered = detail.lower()
    if status_code == 404:
        message = "Telegram respondió 404 Not Found. Revisa que el bot token sea correcto, esté completo y no tenga espacios."
    elif "chat not found" in lowered:
        message = "Telegram respondió 'chat not found'. Abre el chat con tu bot, envía /start y usa el chat id correcto."
    elif "bot was blocked" in lowered:
        message = "Telegram indica que el bot fue bloqueado por el usuario. Desbloquéalo e intenta nuevamente."
    elif "user not found" in lowered:
        message = "Telegram no encontró ese usuario/chat. Verifica el chat id o usa un grupo/canal donde el bot ya esté agregado."
    elif "unauthorized" in lowered or "invalid token" in lowered:
        message = "Telegram rechazó el token del bot. Genera uno nuevo con BotFather o copia el token correcto."
    else:
        message = f"Telegram no aceptó el mensaje: {detail or 'error no especificado'}"
    return TelegramDeliveryError(message, status_code=status_code, description=detail or message)


def _raise_for_telegram_response(response) -> None:
    status_code = getattr(response, "status_code", None)
    try:
        payload = response.json()
    except Exception:
        payload = None
    ok = bool((payload or {}).get("ok")) if isinstance(payload, dict) else False
    if status_code and 200 <= int(status_code) < 300 and (ok or payload is None):
        return
    description = ""
    if isinstance(payload, dict):
        description = str(payload.get("description") or payload.get("error_code") or "")
    if not description:
        description = getattr(response, "text", "") or ""
    raise _build_telegram_error(status_code, description[:500])


def _post_telegram_message(*, token: str, chat_id: str, message: str, timeout: float = 6.0) -> bool:
    if not token or not chat_id:
        return False
    payload = {
        "chat_id": chat_id,
        "text": _safe_telegram_text(message),
        "disable_web_page_preview": True,
    }
    with httpx.Client(timeout=timeout) as client:
        response = client.post(_compose_telegram_url(token), json=payload)
        _raise_for_telegram_response(response)
    return True


def user_has_telegram_config(user: User) -> bool:
    if not user.telegram_alerts_enabled:
        return False
    token = (decrypt_payload(user.telegram_bot_token_encrypted).get("value") or "").strip()
    chat_id = (decrypt_payload(user.telegram_chat_id_encrypted).get("value") or "").strip()
    return bool(token and chat_id)


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
            _raise_for_telegram_response(response)
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
            _raise_for_telegram_response(response)
        return True
    except Exception:
        logger.exception("Failed sending sync Telegram alert")
        return False


def send_admin_user_alert_sync(user: User | None, message: str, *, scope: str = "user-event") -> bool:
    identity = "-"
    if user is not None:
        identity = (
            getattr(user, "name", "")
            or getattr(user, "email", "")
            or f"user_id={getattr(user, 'id', '?')}"
        )
        identity = identity.strip()
    header = f"👤 Usuario: {identity}\n🧭 Scope: {scope}\n"
    return send_telegram_alert_sync(f"{header}{message}")


def send_user_telegram_alert(user: User, message: str, *, raise_on_error: bool = False) -> bool:
    if not user.telegram_alerts_enabled:
        return False

    token = (decrypt_payload(user.telegram_bot_token_encrypted).get("value") or "").strip()
    chat_id = (decrypt_payload(user.telegram_chat_id_encrypted).get("value") or "").strip()
    if not token or not chat_id:
        return False

    try:
        return _post_telegram_message(token=token, chat_id=chat_id, message=message)
    except TelegramDeliveryError:
        logger.exception("Telegram rejected message for user_id=%s", user.id)
        if raise_on_error:
            raise
        return False
    except Exception:
        logger.exception("Failed sending user Telegram alert for user_id=%s", user.id)
        if raise_on_error:
            raise
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
                                  strategy_slug: str, message: str, pnl: float | None = None,
                                  close_reason: str | None = None) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    locale = normalize_alert_locale(locale)
    pnl_line_en = f"Realized PnL: {pnl:.8f}\n" if pnl is not None else ""
    pnl_line_pt = f"PnL realizado: {pnl:.8f}\n" if pnl is not None else ""
    pnl_line_fr = f"PnL réalisé: {pnl:.8f}\n" if pnl is not None else ""
    pnl_line_es = f"PnL realizado: {pnl:.8f}\n" if pnl is not None else ""
    close_line_en = f"Close reason: {close_reason}\n" if close_reason else ""
    close_line_pt = f"Motivo do fechamento: {close_reason}\n" if close_reason else ""
    close_line_fr = f"Motif de clôture: {close_reason}\n" if close_reason else ""
    close_line_es = f"Motivo de cierre: {close_reason}\n" if close_reason else ""
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
            f"{pnl_line_en}"
            f"{close_line_en}"
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
            f"{pnl_line_pt}"
            f"{close_line_pt}"
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
            f"{pnl_line_fr}"
            f"{close_line_fr}"
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
        f"{pnl_line_es}"
        f"{close_line_es}"
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


def format_user_info_message(*, locale: str, title: str, detail: str, connector_label: str | None = None,
                             platform: str | None = None, symbol: str | None = None) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    locale = normalize_alert_locale(locale)
    where = f"{connector_label} ({platform})" if connector_label and platform else "-"
    pair = symbol or "-"
    if locale == "en":
        return (
            f"ℹ️ {title}\n"
            f"Time: {now}\n"
            f"Connector: {where}\n"
            f"Pair: {pair}\n"
            f"Details: {detail}"
        )
    if locale == "pt":
        return (
            f"ℹ️ {title}\n"
            f"Horário: {now}\n"
            f"Conector: {where}\n"
            f"Par: {pair}\n"
            f"Detalhes: {detail}"
        )
    if locale == "fr":
        return (
            f"ℹ️ {title}\n"
            f"Heure: {now}\n"
            f"Connecteur: {where}\n"
            f"Pair: {pair}\n"
            f"Détails: {detail}"
        )
    return (
        f"ℹ️ {title}\n"
        f"Hora: {now}\n"
        f"Conector: {where}\n"
        f"Par: {pair}\n"
        f"Detalle: {detail}"
    )


def send_user_telegram_test_alert(user: User, *, raise_on_error: bool = False) -> bool:
    locale = normalize_alert_locale(user.alert_language)
    display_name = user.name or user.email or f"user_id={user.id}"
    title = {
        "en": "Telegram notifications validated",
        "pt": "Notificações do Telegram validadas",
        "fr": "Notifications Telegram validées",
    }.get(locale, "Notificaciones de Telegram validadas")
    detail = {
        "en": f"Hello {display_name}. Your account is ready to receive executions, errors, balances and operational updates.",
        "pt": f"Olá {display_name}. Sua conta está pronta para receber execuções, erros, saldos e atualizações operacionais.",
        "fr": f"Bonjour {display_name}. Votre compte est prêt à recevoir exécutions, erreurs, soldes et mises à jour opérationnelles.",
    }.get(locale, f"Hola {display_name}. Tu cuenta quedó lista para recibir ejecuciones, errores, saldos y actualizaciones operativas.")
    return send_user_telegram_alert(user, format_user_info_message(locale=locale, title=title, detail=detail), raise_on_error=raise_on_error)
