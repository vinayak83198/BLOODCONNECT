"""Email delivery for verification and password-reset links.








Configure SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM_EMAIL,
SMTP_USE_TLS, and FRONTEND_BASE_URL in the environment before using in production.
For Gmail, use an App Password; never put credentials in source control.
"""
import os
import smtplib
from email.message import EmailMessage
from fastapi import HTTPException, status


def send_email(to_email: str, subject: str, text_body: str, html_body: str | None = None) -> None:
    host = os.getenv("SMTP_HOST")
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM_EMAIL") or username
    if not host or not username or not password or not from_email:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email delivery is not configured. Set the SMTP environment variables, then request the email again.",
        )

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    try:
        port = int(os.getenv("SMTP_PORT", "587"))
        timeout = float(os.getenv("SMTP_TIMEOUT_SECONDS", "15"))
        if os.getenv("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes"):
            with smtplib.SMTP(host, port, timeout=timeout) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(username, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP_SSL(host, port, timeout=timeout) as server:
                server.login(username, password)
                server.send_message(msg)
    except (OSError, smtplib.SMTPException, ValueError) as exc:
        print(f"EMAIL ERROR: {type(exc).__name__}: {exc}", flush=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="We could not send the email right now. Check SMTP settings and try again.",
        ) from exc
