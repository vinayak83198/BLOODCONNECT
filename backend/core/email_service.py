
"""Email delivery for verification and password-reset links using Brevo API."""

import os

import httpx
from fastapi import HTTPException, status


BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def send_email(
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
) -> None:
    """Send a transactional email using the Brevo HTTP API."""

    api_key = os.getenv("BREVO_API_KEY")
    from_email = os.getenv("BREVO_SENDER_EMAIL")
    from_name = os.getenv("BREVO_SENDER_NAME", "BloodConnect")

    if not api_key or not from_email:
        print(
            "BREVO ERROR: BREVO_API_KEY or BREVO_SENDER_EMAIL is missing.",
            flush=True,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email delivery is not configured.",
        )

    payload = {
        "sender": {
            "name": from_name,
            "email": from_email,
        },
        "to": [
            {"email": to_email}
        ],
        "subject": subject,
        "textContent": text_body,
    }

    if html_body:
        payload["htmlContent"] = html_body

    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json",
    }

    try:
        response = httpx.post(
            BREVO_API_URL,
            headers=headers,
            json=payload,
            timeout=20.0,
        )
        response.raise_for_status()

    except httpx.HTTPStatusError as exc:
        # Do not print the API key or the full response body.
        print(
            f"BREVO ERROR: HTTP {exc.response.status_code}",
            flush=True,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="We could not send the email right now. Please try again.",
        ) from exc

    except httpx.RequestError as exc:
        print(
            f"BREVO CONNECTION ERROR: {type(exc).__name__}",
            flush=True,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="We could not send the email right now. Please try again.",
        ) from exc
