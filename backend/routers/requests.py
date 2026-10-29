
"""
routers/requests.py — Blood request endpoints.

Contact details stay private until a donor accepts a request.
Telegram notifications are sent to linked, compatible, available,
eligible donors who are within the request radius.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from core.auth import get_current_user
from core.database import find_one, insert, next_id, read_all, update_one
from models import BloodRequestCreate, BloodRequestOut, IncomingRequestOut
from utils.matching import can_donate_to, haversine_km, is_donation_eligible
from utils.telegram_service import send_telegram_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/requests", tags=["requests"])


def _to_request_out(req: dict) -> BloodRequestOut:
    accepted_by_name = None
    accepted_by_phone = None

    if req.get("accepted_by"):
        donor = find_one("users", user_id=req["accepted_by"])
        if donor:
            accepted_by_name = donor.get("name")
            accepted_by_phone = donor.get("phone")

    return BloodRequestOut(
        request_id=req["request_id"],
        recipient_id=req["recipient_id"],
        recipient_name=req["recipient_name"],
        blood_group=req["blood_group"],
        units_needed=req["units_needed"],
        hospital_name=req["hospital_name"],
        urgency=req["urgency"],
        radius_km=req["radius_km"],
        notes=req.get("notes"),
        status=req["status"],
        created_at=req["created_at"],
        accepted_by=req.get("accepted_by"),
        accepted_by_name=accepted_by_name,
        accepted_by_phone=accepted_by_phone,
    )


def _notify_matching_donors(request: dict) -> None:
    """Notify linked donors who match a newly created blood request."""
    for donor in read_all("users"):
        if donor.get("role") not in ("donor", "both"):
            continue

        if donor.get("user_id") == request["recipient_id"]:
            continue

        if not donor.get("available", True):
            continue

        chat_id = donor.get("telegram_chat_id")
        if not chat_id:
            continue

        if not is_donation_eligible(donor.get("last_donation_date")):
            continue

        if not can_donate_to(
            donor.get("blood_group"),
            request["blood_group"],
        ):
            continue

        try:
            distance = haversine_km(
                request["recipient_latitude"],
                request["recipient_longitude"],
                donor["latitude"],
                donor["longitude"],
            )
        except (KeyError, TypeError, ValueError):
            logger.warning(
                "Skipping donor with missing or invalid location: %s",
                donor.get("user_id"),
            )
            continue

        if distance > request["radius_km"]:
            continue

        message = (
            "🩸 BloodConnect — New Blood Request\n\n"
            f"Blood group needed: {request['blood_group']}\n"
            f"Units needed: {request['units_needed']}\n"
            f"Hospital: {request['hospital_name']}\n"
            f"Urgency: {request['urgency']}\n"
            f"Distance: {distance:.1f} km\n\n"
            "Please open BloodConnect to view the request and respond."
        )

        try:
            sent = send_telegram_message(chat_id, message)
            if sent:
                logger.info(
                    "Telegram notification sent for request %s to donor %s",
                    request["request_id"],
                    donor.get("user_id"),
                )
            else:
                logger.warning(
                    "Telegram notification was not delivered to donor %s",
                    donor.get("user_id"),
                )
        except Exception:
            # A Telegram failure must not undo a successfully created request.
            logger.exception(
                "Telegram notification failed for donor %s",
                donor.get("user_id"),
            )


@router.post(
    "",
    response_model=BloodRequestOut,
    status_code=status.HTTP_201_CREATED,
)
def create_request(
    payload: BloodRequestCreate,
    current_user: dict = Depends(get_current_user),
) -> BloodRequestOut:
    if current_user["role"] not in ("recipient", "both"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only recipient accounts can create a blood request.",
        )

    request = {
        "request_id": next_id("requests", "request_id", "req_"),
        "recipient_id": current_user["user_id"],
        "recipient_name": current_user["name"],
        "recipient_latitude": current_user["latitude"],
        "recipient_longitude": current_user["longitude"],
        "blood_group": payload.blood_group,
        "units_needed": payload.units_needed,
        "hospital_name": payload.hospital_name.strip(),
        "urgency": payload.urgency,
        "radius_km": payload.radius_km,
        "notes": payload.notes,
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "accepted_by": None,
    }

    insert("requests", request)

    # Notify matching Telegram-linked donors without failing request creation.
    _notify_matching_donors(request)

    return _to_request_out(request)


@router.get("/mine", response_model=list[BloodRequestOut])
def my_requests(
    current_user: dict = Depends(get_current_user),
) -> list[BloodRequestOut]:
    mine = [
        request
        for request in read_all("requests")
        if request["recipient_id"] == current_user["user_id"]
    ]
    mine.sort(key=lambda request: request["created_at"], reverse=True)
    return [_to_request_out(request) for request in mine]


@router.get("/incoming", response_model=list[IncomingRequestOut])
def incoming_requests(
    current_user: dict = Depends(get_current_user),
) -> list[IncomingRequestOut]:
    """Return open requests matching this donor's eligibility and location."""
    if current_user["role"] not in ("donor", "both"):
        return []

    eligible_now = is_donation_eligible(
        current_user.get("last_donation_date")
    )
    if not eligible_now or not current_user.get("available", True):
        return []

    matches: list[IncomingRequestOut] = []

    for request in read_all("requests"):
        if request["status"] != "open":
            continue

        if request["recipient_id"] == current_user["user_id"]:
            continue

        if not can_donate_to(
            current_user["blood_group"],
            request["blood_group"],
        ):
            continue

        distance = haversine_km(
            request["recipient_latitude"],
            request["recipient_longitude"],
            current_user["latitude"],
            current_user["longitude"],
        )

        if distance > request["radius_km"]:
            continue

        matches.append(
            IncomingRequestOut(
                request_id=request["request_id"],
                recipient_name=request["recipient_name"],
                blood_group=request["blood_group"],
                units_needed=request["units_needed"],
                hospital_name=request["hospital_name"],
                urgency=request["urgency"],
                distance_km=round(distance, 2),
                notes=request.get("notes"),
                created_at=request["created_at"],
                status=request["status"],
            )
        )

    matches.sort(key=lambda match: match.distance_km)
    return matches


@router.post("/{request_id}/accept", response_model=BloodRequestOut)
def accept_request(
    request_id: str,
    current_user: dict = Depends(get_current_user),
) -> BloodRequestOut:
    if current_user["role"] not in ("donor", "both"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only donor accounts can accept a request.",
        )

    request = find_one("requests", request_id=request_id)

    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found",
        )

    if request["status"] != "open":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This request has already been matched or closed.",
        )

    if not can_donate_to(
        current_user["blood_group"],
        request["blood_group"],
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your blood group is not compatible with this request.",
        )

    if not is_donation_eligible(current_user.get("last_donation_date")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You're inside the 90-day donation window and can't accept yet.",
        )

    updated = update_one(
        "requests",
        request_id,
        "request_id",
        {
            "status": "matched",
            "accepted_by": current_user["user_id"],
        },
    )

    # Notify both donor and recipient after the request is successfully matched.
    # Notification failures must never undo the successful match.
    try:
        requester = find_one("users", user_id=request["recipient_id"])

        donor_chat_id = current_user.get("telegram_chat_id")
        recipient_chat_id = requester.get("telegram_chat_id") if requester else None

        latitude = request.get("recipient_latitude")
        longitude = request.get("recipient_longitude")
        if latitude is not None and longitude is not None:
            map_link = f"https://www.google.com/maps?q={latitude},{longitude}"
        else:
            map_link = "Location coordinates are not available."

        donor_message = (
            "🩸 BloodConnect — Your request was accepted!\n\n"
            f"Recipient: {request.get('recipient_name', 'Recipient')}\n"
            f"Recipient phone: {requester.get('phone', 'Not available') if requester else 'Not available'}\n"
            f"Blood group needed: {request['blood_group']}\n"
            f"Units needed: {request['units_needed']}\n"
            f"Hospital: {request['hospital_name']}\n"
            f"Location: {map_link}\n"
            f"Urgency: {request['urgency']}\n\n"
            "Please contact the recipient to coordinate the donation."
        )

        recipient_message = (
            "🩸 BloodConnect — A donor has accepted your request!\n\n"
            f"Donor: {current_user.get('name', 'Donor')}\n"
            f"Donor phone: {current_user.get('phone', 'Not available')}\n"
            f"Donor blood group: {current_user.get('blood_group', 'Not available')}\n"
            f"Blood group needed: {request['blood_group']}\n"
            f"Units needed: {request['units_needed']}\n"
            f"Hospital: {request['hospital_name']}\n"
            f"Urgency: {request['urgency']}\n\n"
            "Please contact the donor to coordinate the donation."
        )

        if donor_chat_id:
            if not send_telegram_message(donor_chat_id, donor_message):
                logger.warning(
                    "Telegram notification failed for donor %s",
                    current_user.get("user_id"),
                )
        else:
            logger.warning(
                "Donor %s has no linked Telegram chat",
                current_user.get("user_id"),
            )

        if recipient_chat_id:
            if not send_telegram_message(recipient_chat_id, recipient_message):
                logger.warning(
                    "Telegram notification failed for recipient of request %s",
                    request_id,
                )
        else:
            logger.warning(
                "Recipient of request %s has no linked Telegram chat",
                request_id,
            )
    except Exception:
        logger.exception(
            "Telegram notification failed after matching request %s",
            request_id,
        )

    return _to_request_out(updated)


@router.post("/{request_id}/fulfill", response_model=BloodRequestOut)
def fulfill_request(
    request_id: str,
    current_user: dict = Depends(get_current_user),
) -> BloodRequestOut:
    """Mark a matched request as fulfilled after donation."""
    request = find_one("requests", request_id=request_id)

    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found",
        )

    if request["recipient_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not your request",
        )

    if request["status"] != "matched":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Request isn't in a matched state",
        )

    updated = update_one(
        "requests",
        request_id,
        "request_id",
        {"status": "fulfilled"},
    )

    if request.get("accepted_by"):
        update_one(
            "users",
            request["accepted_by"],
            "user_id",
            {
                "last_donation_date": datetime.now(timezone.utc)
                .date()
                .isoformat()
            },
        )

    return _to_request_out(updated)
