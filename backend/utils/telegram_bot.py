
import asyncio
import hashlib
import logging
import os
from datetime import datetime, timezone

import httpx

from core.database import find_one, update_one

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"
BOT_USERNAME = "BloodConnectAlertsBot"


async def send_bot_message(
    client: httpx.AsyncClient,
    token: str,
    chat_id: int,
    text: str,
) -> None:
    response = await client.post(
        f"{TELEGRAM_API}/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text},
    )
    response.raise_for_status()


async def handle_start(
    client: httpx.AsyncClient,
    token: str,
    message: dict,
) -> None:
    chat = message.get("chat", {})
    sender = message.get("from", {})
    chat_id = chat.get("id")
    text = message.get("text", "").strip()

    if not chat_id or chat.get("type") != "private":
        return

    parts = text.split(maxsplit=1)
    code = parts[1].strip() if len(parts) == 2 else ""

    if not code:
        await send_bot_message(
            client,
            token,
            chat_id,
            "Welcome to BloodConnect! To connect your account, "
            "open the Telegram linking link from your logged-in "
            "BloodConnect account.",
        )
        return

    code_hash = hashlib.sha256(code.encode()).hexdigest()
    link_record = find_one("telegram_link_tokens", code_hash=code_hash)

    if not link_record or link_record.get("used"):
        await send_bot_message(
            client, token, chat_id,
            "This linking code is invalid or already used. "
            "Please generate a new link in BloodConnect.",
        )
        return

    try:
        expiry = datetime.fromisoformat(
            link_record["expires_at"].replace("Z", "+00:00")
        )
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
    except (KeyError, ValueError):
        await send_bot_message(
            client, token, chat_id,
            "This linking code is invalid. Please generate a new one.",
        )
        return

    if datetime.now(timezone.utc) >= expiry:
        await send_bot_message(
            client, token, chat_id,
            "This linking code has expired. Generate a new link in BloodConnect.",
        )
        return

    user_id = link_record.get("user_id")
    user = find_one("users", user_id=user_id)

    if not user:
        await send_bot_message(
            client, token, chat_id,
            "Your BloodConnect account could not be found. Please log in again.",
        )
        return

    # Claim the one-time code before saving the Telegram account.
    claimed = update_one(
        "telegram_link_tokens",
        code_hash,
        "code_hash",
        {"used": True},
    )
    if not claimed:
        return

    updated_user = update_one(
        "users",
        user_id,
        "user_id",
        {
            "telegram_chat_id": str(chat_id),
            "telegram_username": sender.get("username"),
        },
    )

    if not updated_user:
        await send_bot_message(
            client, token, chat_id,
            "Account linking failed. Please try again from BloodConnect.",
        )
        return

    await send_bot_message(
        client,
        token,
        chat_id,
        "✅ Your Telegram account is now linked to BloodConnect! "
        "You can receive blood-request notifications here.",
    )


async def telegram_polling_loop() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.warning("Telegram bot is disabled: TELEGRAM_BOT_TOKEN is not set.")
        return

    offset = 0
    timeout = httpx.Timeout(35.0, connect=10.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        logger.info("BloodConnect Telegram bot polling started.")

        while True:
            try:
                response = await client.get(
                    f"{TELEGRAM_API}/bot{token}/getUpdates",
                    params={"timeout": 25, "offset": offset},
                    timeout=timeout,
                )
                response.raise_for_status()
                result = response.json()

                if not result.get("ok"):
                    logger.error("Telegram getUpdates returned an unsuccessful response.")
                    await asyncio.sleep(3)
                    continue

                for update in result.get("result", []):
                    offset = update["update_id"] + 1
                    message = update.get("message", {})
                    text = message.get("text", "").strip()

                    if text == "/start" or text.startswith("/start "):
                        try:
                            await handle_start(client, token, message)
                        except (httpx.HTTPError, ValueError):
                            logger.exception("Failed to process a Telegram start message.")

            except asyncio.CancelledError:
                raise
            except httpx.HTTPError:
                logger.exception("Telegram polling request failed.")
                await asyncio.sleep(5)
