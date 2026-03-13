from __future__ import annotations

from datetime import datetime, timezone
import logging

import httpx

from app.core import settings

logger = logging.getLogger(__name__)


async def send_telegram_alert(message: str) -> bool:
    token = (settings.telegram_admin_bot_token or "").strip()
    chat_id = (settings.telegram_admin_chat_id or "").strip()
    if not token or not chat_id:
        return False

    safe_message = message[:3900]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": safe_message,
        "disable_web_page_preview": True,
    }

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
        return True
    except Exception:
        logger.exception("Failed sending Telegram alert")
        return False


def format_failure_message(scope: str, detail: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return (
        "🚨 TradingSaas Failure Alert\n"
        f"Time: {now}\n"
        f"Scope: {scope}\n"
        f"Detail: {detail}"
    )
