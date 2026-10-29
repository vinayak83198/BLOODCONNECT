"""Authentication, email verification, and password recovery routes."""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, status

from core.auth import create_access_token, get_current_user, hash_password, verify_password
from core.database import find_one, insert, next_id, read_all, write_all
from core.email_service import send_email
from models import (
    EmailRequest, PasswordResetRequest, SignupResponse, TokenOut, UserLogin,
    UserOut, UserSignup, TokenRequest, LoginOtpVerify,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
TOKEN_TTL_MINUTES = 30
LOGIN_OTP_TTL_MINUTES = 5
LOGIN_OTP_MAX_ATTEMPTS = 5
LOGIN_OTP_RESEND_SECONDS = 30
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://127.0.0.1:5500").rstrip("/")


def _to_user_out(user: dict) -> UserOut:
    return UserOut(
        user_id=user["user_id"], name=user["name"], email=user["email"],
        phone=user["phone"], role=user["role"], blood_group=user["blood_group"],
        city=user["city"], latitude=user["latitude"], longitude=user["longitude"],
        available=user.get("available", True),
        last_donation_date=user.get("last_donation_date"),
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _create_action_token(user_id: str, purpose: str) -> str:
    raw_token = secrets.token_urlsafe(32)
    expires = (_now() + timedelta(minutes=TOKEN_TTL_MINUTES)).isoformat()
    # Invalidate previous unused tokens for this user and purpose.
    records = read_all("auth_tokens")
    for record in records:
        if record.get("user_id") == user_id and record.get("purpose") == purpose:
            record["used"] = True
    records.append({
        "token_id": next_id("auth_tokens", "token_id", "tok_"),
        "user_id": user_id,
        "purpose": purpose,
        "token_hash": _token_digest(raw_token),
        "expires_at": expires,
        "used": False,
    })
    write_all("auth_tokens", records)
    return raw_token


def _consume_action_token(raw_token: str, purpose: str) -> dict:
    digest = _token_digest(raw_token)
    records = read_all("auth_tokens")
    match = None
    for record in records:
        if record.get("token_hash") == digest and record.get("purpose") == purpose:
            match = record
            break
    if not match or match.get("used"):
        raise HTTPException(status_code=400, detail="This link is invalid or has already been used.")
    try:
        expiry = datetime.fromisoformat(match["expires_at"])
    except (KeyError, ValueError):
        raise HTTPException(status_code=400, detail="This link is invalid. Please request a new one.")
    if expiry <= _now():
        match["used"] = True
        write_all("auth_tokens", records)
        raise HTTPException(status_code=400, detail="This link has expired. Please request a new one.")
    match["used"] = True
    write_all("auth_tokens", records)
    user = find_one("users", user_id=match.get("user_id"))
    if not user:
        raise HTTPException(status_code=400, detail="This link is no longer valid.")
    return user


def _send_verification_email(user: dict) -> None:
    token = _create_action_token(user["user_id"], "verify_email")
    link = f"{FRONTEND_BASE_URL}/verify-email.html?token={quote(token)}"
    send_email(
        user["email"],
        "Verify your BloodConnect email",
        f"Hello {user['name']},\n\nVerify your BloodConnect account by opening this link:\n{link}\n\nThis link expires in {TOKEN_TTL_MINUTES} minutes. If you did not create this account, ignore this email.",
        f"<p>Hello {user['name']},</p><p>Verify your BloodConnect account:</p><p><a href=\"{link}\">Verify email address</a></p><p>This link expires in {TOKEN_TTL_MINUTES} minutes.</p>",
    )


def _send_reset_email(user: dict) -> None:
    token = _create_action_token(user["user_id"], "reset_password")
    link = f"{FRONTEND_BASE_URL}/reset-password.html?token={quote(token)}"
    send_email(
        user["email"],
        "Reset your BloodConnect password",
        f"Hello {user['name']},\n\nReset your BloodConnect password using this link:\n{link}\n\nThis link expires in {TOKEN_TTL_MINUTES} minutes. If you did not request this, ignore this email.",
        f"<p>Hello {user['name']},</p><p>Reset your BloodConnect password:</p><p><a href=\"{link}\">Reset password</a></p><p>This link expires in {TOKEN_TTL_MINUTES} minutes.</p>",
    )


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: UserSignup) -> SignupResponse:
    if not payload.accepted_terms:
        raise HTTPException(status_code=400, detail="You must accept the Terms & Conditions to create an account.")
    existing = find_one("users", email=payload.email.lower())
    if existing is not None:
        if not existing.get("email_verified", True):
            _send_verification_email(existing)
            return SignupResponse(message="This account already exists but is not verified. A new verification email was sent.", email=existing["email"])
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")

    user = {
        "user_id": next_id("users", "user_id", "usr_"),
        "name": payload.name.strip(),
        "email": payload.email.lower(),
        "password_hash": hash_password(payload.password),
        "phone": payload.phone.strip(),
        "role": payload.role,
        "blood_group": payload.blood_group,
        "city": payload.city.strip(),
        "latitude": payload.latitude,
        "longitude": payload.longitude,
        "available": True,
        "last_donation_date": None,
        "email_verified": False,
        "terms_accepted_at": _now().isoformat(),
    }
    insert("users", user)
    _send_verification_email(user)
    return SignupResponse(message="Account created. Check your email and verify your address before logging in.", email=user["email"])


@router.post("/login", response_model=SignupResponse)
def login(payload: UserLogin) -> SignupResponse:
    """Check password and send a short-lived OTP; do not issue a session yet."""
    email = payload.email.lower()
    user = find_one("users", email=email)
    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password.")
    if not user.get("email_verified", True):
        raise HTTPException(status_code=403, detail="Please verify your email address first. Use Resend verification email if needed.")

    records = read_all("login_otps")
    now = _now()
    # Avoid repeatedly sending OTPs to the same account.
    previous = next((r for r in reversed(records) if r.get("user_id") == user["user_id"] and not r.get("used")), None)
    if previous:
        try:
            last_sent = datetime.fromisoformat(previous["created_at"])
            if (now - last_sent).total_seconds() < LOGIN_OTP_RESEND_SECONDS:
                raise HTTPException(status_code=429, detail="Please wait 30 seconds before requesting another login OTP.")
        except (KeyError, ValueError):
            pass
        previous["used"] = True

    otp = f"{secrets.randbelow(1_000_000):06d}"
    records.append({
        "otp_id": next_id("login_otps", "otp_id", "otp_"),
        "user_id": user["user_id"],
        "email": email,
        "otp_hash": _token_digest(otp),
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=LOGIN_OTP_TTL_MINUTES)).isoformat(),
        "attempts": 0,
        "used": False,
    })
    write_all("login_otps", records)
    send_email(
        email,
        "Your BloodConnect login OTP",
        f"Hello {user['name']},\n\nYour BloodConnect login OTP is: {otp}\nIt expires in {LOGIN_OTP_TTL_MINUTES} minutes. Do not share it with anyone. If you did not try to log in, you can ignore this email.",
        f"<p>Hello {user['name']},</p><p>Your BloodConnect login OTP is:</p><p style=\"font-size:28px;font-weight:bold;letter-spacing:6px\">{otp}</p><p>This OTP expires in {LOGIN_OTP_TTL_MINUTES} minutes. Do not share it with anyone.</p>",
    )
    return SignupResponse(message=f"A 6-digit login OTP was sent to {email}. It expires in {LOGIN_OTP_TTL_MINUTES} minutes.", email=email)


@router.post("/verify-login-otp", response_model=TokenOut)
def verify_login_otp(payload: LoginOtpVerify) -> TokenOut:
    email = payload.email.lower()
    records = read_all("login_otps")
    record = next((r for r in reversed(records) if r.get("email") == email and not r.get("used")), None)
    if not record:
        raise HTTPException(status_code=400, detail="No active login OTP found. Log in again to request a new OTP.")
    if int(record.get("attempts", 0)) >= LOGIN_OTP_MAX_ATTEMPTS:
        record["used"] = True
        write_all("login_otps", records)
        raise HTTPException(status_code=429, detail="Too many incorrect OTP attempts. Please log in again.")
    try:
        expiry = datetime.fromisoformat(record["expires_at"])
    except (KeyError, ValueError):
        record["used"] = True
        write_all("login_otps", records)
        raise HTTPException(status_code=400, detail="OTP is invalid. Please log in again.")
    if expiry <= _now():
        record["used"] = True
        write_all("login_otps", records)
        raise HTTPException(status_code=400, detail="OTP expired. Please log in again to request a new one.")
    if not secrets.compare_digest(record.get("otp_hash", ""), _token_digest(payload.otp)):
        record["attempts"] = int(record.get("attempts", 0)) + 1
        if record["attempts"] >= LOGIN_OTP_MAX_ATTEMPTS:
            record["used"] = True
        write_all("login_otps", records)
        raise HTTPException(status_code=400, detail=f"Incorrect OTP. {max(0, LOGIN_OTP_MAX_ATTEMPTS - int(record['attempts']))} attempts remaining.")

    record["used"] = True
    write_all("login_otps", records)
    user = find_one("users", email=email)
    if not user or not user.get("email_verified", True):
        raise HTTPException(status_code=403, detail="Please verify your email address before logging in.")
    token = create_access_token(subject=user["user_id"])
    return TokenOut(access_token=token, user=_to_user_out(user))


@router.post("/verify-email", response_model=SignupResponse)
def verify_email(payload: TokenRequest) -> SignupResponse:
    user = _consume_action_token(payload.token, "verify_email")
    user["email_verified"] = True
    # Persist through a full collection write because user records use JSON storage.
    users = read_all("users")
    for record in users:
        if record.get("user_id") == user["user_id"]:
            record["email_verified"] = True
            break
    write_all("users", users)
    return SignupResponse(message="Email verified successfully. You can now log in.", email=user["email"])


@router.post("/resend-verification", response_model=SignupResponse)
def resend_verification(payload: EmailRequest) -> SignupResponse:
    user = find_one("users", email=payload.email.lower())
    if user and user.get("email_verified") is not True:
        _send_verification_email(user)
    # Same message whether or not the address exists to reduce account enumeration.
    return SignupResponse(message="If this account needs verification, a verification email has been sent.", email=payload.email.lower())


@router.post("/forgot-password", response_model=SignupResponse)
def forgot_password(payload: EmailRequest) -> SignupResponse:
    user = find_one("users", email=payload.email.lower())
    if user:
        _send_reset_email(user)
    return SignupResponse(message="If an account exists for this email, password-reset instructions have been sent.", email=payload.email.lower())


@router.post("/reset-password", response_model=SignupResponse)
def reset_password(payload: PasswordResetRequest) -> SignupResponse:
    user = _consume_action_token(payload.token, "reset_password")
    user["password_hash"] = hash_password(payload.new_password)
    users = read_all("users")
    for record in users:
        if record.get("user_id") == user["user_id"]:
            record["password_hash"] = user["password_hash"]
            break
    write_all("users", users)
    return SignupResponse(message="Password changed successfully. You can now log in.", email=user["email"])


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: dict = Depends(get_current_user)) -> UserOut:
    return _to_user_out(current_user)
