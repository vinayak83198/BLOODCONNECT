"""
routers/donors.py — Search module: radius filter + Haversine ranking,
as described on the Screenshots & Code Walkthrough slide.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.auth import get_current_user
from core.database import read_all, update_one
from models import DonorProfileUpdate, DonorSearchResult, UserOut
from routers.auth import _to_user_out
from utils.matching import (
    VALID_BLOOD_GROUPS,
    can_donate_to,
    haversine_km,
    is_donation_eligible,
    next_eligible_date,
)

router = APIRouter(prefix="/api/donors", tags=["donors"])


@router.get("/me", response_model=UserOut)
def get_my_profile(current_user: dict = Depends(get_current_user)) -> UserOut:
    return _to_user_out(current_user)


@router.put("/me", response_model=UserOut)
def update_my_profile(
    payload: DonorProfileUpdate,
    current_user: dict = Depends(get_current_user),
) -> UserOut:
    patch = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not patch:
        return _to_user_out(current_user)

    updated = update_one("users", current_user["user_id"], "user_id", patch)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _to_user_out(updated)


@router.get("/search", response_model=list[DonorSearchResult])
def search_donors(
    blood_group: str = Query(..., description="Recipient's blood group, e.g. O+"),
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(10, ge=1, le=100),
    only_available: bool = Query(True),
    current_user: dict = Depends(get_current_user),
) -> list[DonorSearchResult]:
    if blood_group not in VALID_BLOOD_GROUPS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"blood_group must be one of {VALID_BLOOD_GROUPS}",
        )

    results: list[DonorSearchResult] = []
    for user in read_all("users"):
        if user["role"] not in ("donor", "both"):
            continue
        if user["user_id"] == current_user["user_id"]:
            continue
        if not can_donate_to(user["blood_group"], blood_group):
            continue

        distance = haversine_km(latitude, longitude, user["latitude"], user["longitude"])
        if distance > radius_km:
            continue

        eligible = is_donation_eligible(user.get("last_donation_date"))
        available = user.get("available", True)
        if only_available and not (eligible and available):
            continue

        results.append(
            DonorSearchResult(
                user_id=user["user_id"],
                name=user["name"],
                blood_group=user["blood_group"],
                city=user["city"],
                distance_km=round(distance, 2),
                available=available,
                eligible=eligible,
                next_eligible_date=next_eligible_date(user.get("last_donation_date")),
            )
        )

    results.sort(key=lambda r: r.distance_km)
    return results
