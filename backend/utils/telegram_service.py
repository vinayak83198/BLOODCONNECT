
import os
import logging

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


def send_telegram_message(chat_id: str | int, message: str) -> bool:
    """Send a Telegram message. Return False if not configured or delivery fails."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        logger.warning("Telegram notifications are not configured.")
        return False

    url = f"{TELEGRAM_API}/bot{bot_token}/sendMessage"

    try:
        response = httpx.post(
            url,
            json={
                "chat_id": chat_id,
                "text": message,
            },
            timeout=10.0,
        )
        response.raise_for_status()
        return response.json().get("ok", False)
    except (httpx.HTTPError, ValueError):
        logger.exception("Telegram message delivery failed.")
        return False
