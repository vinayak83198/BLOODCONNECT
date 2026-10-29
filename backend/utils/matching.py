"""
Matching utilities: geographic distance, blood-group compatibility,
and the 90-day donation eligibility guard.
"""
from datetime import date
from math import radians, sin, cos, sqrt, atan2

EARTH_RADIUS_KM = 6371.0088

# Which donor blood groups can safely give to a given recipient group.
# Standard ABO/Rh compatibility chart.
COMPATIBLE_DONORS = {
    "O-": ["O-"],
    "O+": ["O+", "O-"],
    "A-": ["A-", "O-"],
    "A+": ["A+", "A-", "O+", "O-"],
    "B-": ["B-", "O-"],
    "B+": ["B+", "B-", "O+", "O-"],
    "AB-": ["AB-", "A-", "B-", "O-"],
    "AB+": ["AB+", "AB-", "A+", "A-", "B+", "B-", "O+", "O-"],
}

VALID_BLOOD_GROUPS = list(COMPATIBLE_DONORS.keys())

MIN_DAYS_BETWEEN_DONATIONS = 90


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points, in kilometres."""
    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi = radians(lat2 - lat1)
    d_lambda = radians(lon2 - lon1)

    a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def can_donate_to(donor_blood_group: str, recipient_blood_group: str) -> bool:
    """True if donor_blood_group is a safe match for recipient_blood_group."""
    eligible_donors = COMPATIBLE_DONORS.get(recipient_blood_group)
    if eligible_donors is None:
        return False
    return donor_blood_group in eligible_donors


def days_since(iso_date_str: str | None) -> int | None:
    """Days between an ISO date string (YYYY-MM-DD) and today. None if unset."""
    if not iso_date_str:
        return None
    try:
        last = date.fromisoformat(iso_date_str)
    except ValueError:
        return None
    return (date.today() - last).days


def is_donation_eligible(last_donation_date: str | None) -> bool:
    """
    A donor is eligible if they have never donated, or if at least
    MIN_DAYS_BETWEEN_DONATIONS days have passed since their last donation.
    """
    elapsed = days_since(last_donation_date)
    if elapsed is None:
        return True
    return elapsed >= MIN_DAYS_BETWEEN_DONATIONS


def next_eligible_date(last_donation_date: str | None) -> str | None:
    """ISO date the donor becomes eligible again, or None if eligible now/never donated."""
    elapsed = days_since(last_donation_date)
    if elapsed is None or elapsed >= MIN_DAYS_BETWEEN_DONATIONS:
        return None
    from datetime import timedelta

    last = date.fromisoformat(last_donation_date)
    return (last + timedelta(days=MIN_DAYS_BETWEEN_DONATIONS)).isoformat()
