"""Doctors / clinicians (mirrors FHIR Practitioner). Slots are NOT stored here:
they come from the mock HealthcareProvider adapter (plan §9)."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdTimestampMixin


class Provider(IdTimestampMixin, Base):
    __tablename__ = "providers"

    name: Mapped[str] = mapped_column(String(120))
    specialty: Mapped[str] = mapped_column(String(80))
    location: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(30))
    # id of this practitioner inside the (mock) external system
    external_ref: Mapped[str] = mapped_column(String(100), unique=True)
