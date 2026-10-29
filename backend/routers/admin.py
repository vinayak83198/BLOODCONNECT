
import os
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, status

from core.auth import get_current_user
from core.database import read_all

router = APIRouter(prefix="/api/admin", tags=["admin"])


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Allow access only to email addresses configured by the server."""
    allowed_emails = {
        email.strip().lower()
        for email in os.getenv("ADMIN_EMAILS", "").split(",")
        if email.strip()
    }

    if current_user.get("email", "").lower() not in allowed_emails:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return current_user


@router.get("/access")
def check_admin_access(
    admin: dict = Depends(require_admin),
) -> dict:
    return {"is_admin": True}


@router.get("/overview")
def admin_overview(
    admin: dict = Depends(require_admin),
) -> dict:
    users = read_all("users")
    requests = read_all("requests")

    donor_count = sum(
        user.get("role") in ("donor", "both")
        for user in users
    )
    recipient_count = sum(
        user.get("role") in ("recipient", "both")
        for user in users
    )
    available_donors = sum(
        user.get("role") in ("donor", "both")
        and user.get("available", True)
        for user in users
    )

    request_statuses = Counter(
        request.get("status", "unknown")
        for request in requests
    )

    blood_groups = Counter(
        user.get("blood_group", "Unknown")
        for user in users
    )

    recent_requests = sorted(
        requests,
        key=lambda request: request.get("created_at", ""),
        reverse=True,
    )[:10]

    # Return only the fields needed for the dashboard.
    recent_requests = [
        {
            "request_id": request.get("request_id"),
            "recipient_name": request.get("recipient_name"),
            "blood_group": request.get("blood_group"),
            "units_needed": request.get("units_needed"),
            "hospital_name": request.get("hospital_name"),
            "urgency": request.get("urgency"),
            "status": request.get("status"),
            "created_at": request.get("created_at"),
        }
        for request in recent_requests
    ]

    return {
        "total_users": len(users),
        "total_donors": donor_count,
        "total_recipients": recipient_count,
        "available_donors": available_donors,
        "total_requests": len(requests),
        "request_statuses": dict(request_statuses),
        "blood_group_distribution": dict(blood_groups),
        "recent_requests": recent_requests,
    }

