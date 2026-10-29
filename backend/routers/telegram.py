
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.auth import get_current_user
from core.database import find_one, insert, read_all, update_one

router = APIRouter(prefix="/api/telegram", tags=["telegram"])

BOT_USERNAME = "BloodConnectAlertsBot"
LINK_EXPIRY_MINUTES = 10


class TelegramLinkOut(BaseModel):
    link: str
    expires_in_minutes: int


@router.post("/link", response_model=TelegramLinkOut)
def create_telegram_link(
    current_user: dict = Depends(get_current_user),
) -> TelegramLinkOut:
    """Create a short-lived, one-time code for linking the current account."""
    code = secrets.token_urlsafe(24)
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(minutes=LINK_EXPIRY_MINUTES)
    ).isoformat()

    insert(
        "telegram_link_tokens",
        {
            "code_hash": code_hash,
            "user_id": current_user["user_id"],
            "expires_at": expires_at,
            "used": False,
        },
    )

    return TelegramLinkOut(
        link=f"https://t.me/{BOT_USERNAME}?start={code}",
        expires_in_minutes=LINK_EXPIRY_MINUTES,
    )


class TelegramStatusOut(BaseModel):
    linked: bool
    username: str | None = None


@router.get("/status", response_model=TelegramStatusOut)
def telegram_status(
    current_user: dict = Depends(get_current_user),
) -> TelegramStatusOut:
    """Report whether the signed-in account has authorized Telegram alerts."""
    user = find_one("users", user_id=current_user["user_id"]) or current_user
    return TelegramStatusOut(
        linked=bool(user.get("telegram_chat_id")),
        username=user.get("telegram_username"),
    )
