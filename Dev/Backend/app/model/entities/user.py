"""PLACEHOLDER: the auth owner defines the real users table (plan §9, §18).
Agree on it together first. Booking only needs users.id and users.timezone."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdTimestampMixin


class User(IdTimestampMixin, Base):
    __tablename__ = "users"

    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))
    preferred_language: Mapped[str] = mapped_column(String(10), default="en")
    timezone: Mapped[str] = mapped_column(String(64), default="America/Los_Angeles")
