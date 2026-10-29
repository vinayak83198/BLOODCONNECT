"""
Pydantic schemas. Centralised here so routers stay thin and every
endpoint gets the same input validation, matching the Data Validation
row on the Technical Challenges slide (schema enforcement rejects
malformed requests at input, before they reach business logic).
"""
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from utils.matching import VALID_BLOOD_GROUPS

Role = Literal["donor", "recipient", "both"]
Urgency = Literal["standard", "urgent", "critical"]
RequestStatus = Literal["open", "matched", "fulfilled", "cancelled"]


def _validate_blood_group(value: str) -> str:
    if value not in VALID_BLOOD_GROUPS:
        raise ValueError(f"blood_group must be one of {VALID_BLOOD_GROUPS}")
    return value


class UserSignup(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone: str = Field(min_length=7, max_length=15)
    role: Role
    blood_group: str
    city: str = Field(min_length=2, max_length=80)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accepted_terms: bool = False

    _check_blood_group = field_validator("blood_group")(_validate_blood_group)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class LoginOtpVerify(BaseModel):
    email: EmailStr
    otp: str = Field(pattern=r"^\d{6}$")


class UserOut(BaseModel):
    user_id: str
    name: str
    email: EmailStr
    phone: str
    role: Role
    blood_group: str
    city: str
    latitude: float
    longitude: float
    available: bool
    last_donation_date: Optional[str] = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class DonorProfileUpdate(BaseModel):
    available: Optional[bool] = None
    last_donation_date: Optional[str] = None
    city: Optional[str] = Field(default=None, min_length=2, max_length=80)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)


class DonorSearchResult(BaseModel):
    user_id: str
    name: str
    blood_group: str
    city: str
    distance_km: float
    available: bool
    eligible: bool
    next_eligible_date: Optional[str] = None


class BloodRequestCreate(BaseModel):
    blood_group: str
    units_needed: int = Field(ge=1, le=20)
    hospital_name: str = Field(min_length=2, max_length=120)
    urgency: Urgency
    radius_km: float = Field(default=10, ge=1, le=50)
    notes: Optional[str] = Field(default=None, max_length=500)

    _check_blood_group = field_validator("blood_group")(_validate_blood_group)


class BloodRequestOut(BaseModel):
    request_id: str
    recipient_id: str
    recipient_name: str
    blood_group: str
    units_needed: int
    hospital_name: str
    urgency: Urgency
    radius_km: float
    notes: Optional[str] = None
    status: RequestStatus
    created_at: str
    accepted_by: Optional[str] = None
    accepted_by_name: Optional[str] = None
    accepted_by_phone: Optional[str] = None
    recipient_phone: Optional[str] = None


class IncomingRequestOut(BaseModel):
    request_id: str
    recipient_name: str
    blood_group: str
    units_needed: int
    hospital_name: str
    urgency: Urgency
    distance_km: float
    notes: Optional[str] = None
    created_at: str
    status: RequestStatus


class AuthMessage(BaseModel):
    message: str


class EmailRequest(BaseModel):
    email: EmailStr


class TokenRequest(BaseModel):
    token: str = Field(min_length=20, max_length=500)


class PasswordResetRequest(TokenRequest):
    new_password: str = Field(min_length=8, max_length=128)


class SignupResponse(BaseModel):
    message: str
    email: EmailStr
