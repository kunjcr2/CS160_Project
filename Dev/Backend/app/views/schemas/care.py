"""JSON shapes for older adult profiles, consents, and pairing."""

import uuid
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.model.entities.consent_grant import SCOPES
from app.views.schemas.auth import UserResponse


class CreateOlderAdultRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=120, examples=["Margaret Lee"])
    preferred_name: str | None = Field(default=None, max_length=60, examples=["Maggie"])
    timezone: str = Field(default="America/Los_Angeles", max_length=64)
    scopes: list[str] = Field(default_factory=list, examples=[["appointments:read"]])

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)  # fails for names that aren't real time zones
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Unknown time zone.") from None
        return value

    @field_validator("scopes")
    @classmethod
    def known_scopes(cls, value: list[str]) -> list[str]:
        unknown = set(value) - set(SCOPES)
        if unknown:
            raise ValueError(f"Unknown scopes: {sorted(unknown)}")
        return value


class ConsentGrantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    older_adult_id: uuid.UUID
    caregiver_id: uuid.UUID
    scopes: list[str]
    created_at: datetime


class OlderAdultCreatedResponse(BaseModel):
    older_adult: UserResponse
    grant: ConsentGrantResponse


class PairingCodeRequest(BaseModel):
    older_adult_id: uuid.UUID


class PairingCodeResponse(BaseModel):
    code: str
    expires_at: datetime


class PairRequest(BaseModel):
    code: str = Field(min_length=8, max_length=20, examples=["1234 5678"])
    device_label: str | None = Field(default=None, max_length=100, examples=["Margaret's iPad"])
