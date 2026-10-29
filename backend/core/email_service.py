
"""Email delivery for verification and password-reset links using Resend."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import HTTPException, status


def send_email(
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str | None = None,
) -> None:
    api_key = os.getenv("RESEND_API_KEY")
    from_email = os.getenv(
        "RESEND_FROM_EMAIL",
        "BloodConnect <onboarding@resend.dev>",
    )

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email delivery is not configured. Please try again later.",
        )

    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "text": text_body,
    }

    if html_body:
        payload["html"] = html_body

    request = Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
       headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "BloodConnect/1.0",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=20) as response:
            response.read()

    except HTTPError as exc:
        # Log the provider response for debugging without exposing the API key.
        error_body = exc.read().decode("utf-8", errors="replace")
        print(
            f"RESEND ERROR: HTTP {exc.code}: {error_body}",
            flush=True,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="We could not send the email right now. Please try again.",
        ) from exc

    except (URLError, TimeoutError, OSError, ValueError) as exc:
        print(
            f"RESEND ERROR: {type(exc).__name__}: {exc}",
            flush=True,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="We could not send the email right now. Please try again.",
        ) from exc
