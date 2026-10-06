"""PB-01 appointments and PB-02 appointment reminders."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, SmallInteger, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdTimestampMixin, status_check

APPOINTMENT_STATUSES = ("booked", "cancelled", "completed")
REMINDER_KINDS = ("day_before", "morning_of", "hour_before")
REMINDER_STATUSES = ("scheduled", "sent", "acknowledged", "cancelled", "failed")


class Appointment(IdTimestampMixin, Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint(status_check("status", APPOINTMENT_STATUSES), name="status"),
        CheckConstraint("ends_at > starts_at", name="ends_after_start"),
        # No double-booking: one *booked* appointment per provider per start time.
        # Cancelled rows don't block the slot (partial unique index).
        Index(
            "uq_appointments_provider_slot_booked",
            "provider_id",
            "starts_at",
            unique=True,
            postgresql_where=text("status = 'booked'"),
        ),
        Index("ix_appointments_user_starts", "user_id", "starts_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("providers.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # UTC
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    location: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="booked")
    external_ref: Mapped[str | None] = mapped_column(String(100))  # booking id in mock provider

    reminders: Mapped[list["AppointmentReminder"]] = relationship(
        back_populates="appointment", cascade="all, delete-orphan"
    )

    def can_cancel(self, now: datetime) -> bool:
        return self.status == "booked" and self.starts_at > now


class AppointmentReminder(IdTimestampMixin, Base):
    __tablename__ = "appointment_reminders"
    __table_args__ = (
        CheckConstraint(status_check("status", REMINDER_STATUSES), name="status"),
        CheckConstraint(status_check("kind", REMINDER_KINDS), name="kind"),
        # Re-running the "AppointmentBooked" subscriber can't create duplicates.
        Index("uq_appointment_reminders_appt_kind", "appointment_id", "kind", unique=True),
        # The worker's query: WHERE status='scheduled' AND due_at <= now()
        Index(
            "ix_appointment_reminders_due",
            "due_at",
            postgresql_where=text("status = 'scheduled'"),
        ),
    )

    appointment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("appointments.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))
    # UTC, computed from the user's local time zone (never "UTC minus 24 h")
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    appointment: Mapped[Appointment] = relationship(back_populates="reminders")
