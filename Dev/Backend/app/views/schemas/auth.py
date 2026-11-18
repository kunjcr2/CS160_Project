"""JSON shapes for auth endpoints. Pydantic checks them before our code runs."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

# Simple email check: something@something.something
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RegisterRequest(BaseModel):
    email: str = Field(max_length=254, pattern=EMAIL_PATTERN)
    # Long passwords are safer. max_length stops huge inputs that make argon2 slow.
    password: str = Field(min_length=12, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)


class LoginRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)
    device_label: str | None = Field(default=None, max_length=100)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """What we send back about a user. password_hash is NOT here, so it can never leak."""

    # from_attributes: lets Pydantic read a SQLAlchemy User object directly.
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    email: str | None
    display_name: str
    preferred_name: str | None
    preferred_language: str
    timezone: str
    speech_rate: float
