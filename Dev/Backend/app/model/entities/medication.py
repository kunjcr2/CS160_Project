"""PB-03 medication reminders: medicines, their schedules, and one row per real dose.

- medications: one medicine for one older adult.
- medication_schedules: WHEN to take it, in the user's LOCAL time (users.timezone),
  e.g. 08:00 every day. Local, so "8 AM" stays 8 AM after daylight saving changes.
- medication_reminders: one row per real dose (date + time, saved in UTC). They are
  generated from the schedules for the next days, then handled by the reminder worker.

Mock/demo data only, never real patients.
"""

import uuid
from datetime import datetime, time

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Time,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdTimestampMixin, status_check

# Days use Python's numbering: 0 = Monday ... 6 = Sunday (datetime.weekday()).
EVERY_DAY = (0, 1, 2, 3, 4, 5, 6)

# plan §6.3: scheduled -> sent -> taken | missed, or cancelled / failed.
MEDICATION_REMINDER_STATUSES = ("scheduled", "sent", "taken", "missed", "cancelled", "failed")


class Medication(IdTimestampMixin, Base):
    """One medicine for one older adult."""

    __tablename__ = "medications"
    __table_args__ = (CheckConstraint("refills_remaining >= 0", name="refills_not_negative"),)

    # Whose medicine. index=True: makes "list my medications" fast.
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))  # e.g. "Metformin"
    dosage: Mapped[str] = mapped_column(String(50))  # e.g. "500 mg"
    instructions: Mapped[str | None] = mapped_column(String(300))  # e.g. "Take with food"
    # For refills (PB-04, Sprint 3). The pharmacy column comes later with the contacts table.
    refills_remaining: Mapped[int] = mapped_column(SmallInteger, default=0)
    # Empty = still taking it. Filled = stopped, so no new reminders are made.
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    schedules: Mapped[list["MedicationSchedule"]] = relationship(
        back_populates="medication", cascade="all, delete-orphan"
    )


class MedicationSchedule(IdTimestampMixin, Base):
    """When to take one medicine: a local time of day, on some days of the week."""

    __tablename__ = "medication_schedules"
    __table_args__ = (
        # At least one day, and only 0..6 ("<@" means "is inside").
        CheckConstraint("cardinality(days_of_week) > 0", name="days_not_empty"),
        CheckConstraint(
            "days_of_week <@ ARRAY[0, 1, 2, 3, 4, 5, 6]::smallint[]", name="days_valid"
        ),
        # The same medicine can't have the same time twice (e.g. two 08:00 rows).
        Index("uq_medication_schedules_med_time", "medication_id", "time_of_day", unique=True),
    )

    medication_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("medications.id", ondelete="CASCADE")
    )
    # LOCAL wall-clock time with NO time zone (e.g. 08:00). The zone is users.timezone.
    time_of_day: Mapped[time] = mapped_column(Time(timezone=False))
    # A PostgreSQL list of small numbers, e.g. [0, 1, 2, 3, 4, 5, 6] = every day.
    days_of_week: Mapped[list[int]] = mapped_column(
        ARRAY(SmallInteger), default=lambda: list(EVERY_DAY)
    )

    medication: Mapped[Medication] = relationship(back_populates="schedules")


class MedicationReminder(IdTimestampMixin, Base):
    """One real dose: take this medicine at this moment (UTC)."""

    __tablename__ = "medication_reminders"
    __table_args__ = (
        CheckConstraint(status_check("status", MEDICATION_REMINDER_STATUSES), name="status"),
        CheckConstraint("attempts >= 0", name="attempts_not_negative"),
        # taken/missed always has a time; every other status never does.
        CheckConstraint(
            "(status IN ('taken', 'missed')) = (confirmed_at IS NOT NULL)",
            name="confirmed_at_matches_status",
        ),
        # Running the dose generator twice can't create the same dose twice.
        Index("uq_medication_reminders_schedule_due", "schedule_id", "due_at", unique=True),
        # The worker's query: WHERE status = 'scheduled' AND due_at <= now()
        Index(
            "ix_medication_reminders_due",
            "due_at",
            postgresql_where=text("status = 'scheduled'"),
        ),
        # The follow-up query: shown but not answered yet (re-prompt, then missed).
        Index(
            "ix_medication_reminders_sent",
            "sent_at",
            postgresql_where=text("status = 'sent'"),
        ),
        # "My doses today" for the app and the caregiver.
        Index("ix_medication_reminders_user_due", "user_id", "due_at"),
    )

    schedule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("medication_schedules.id", ondelete="CASCADE")
    )
    # Copied from the medication, so permission checks and the worker need no joins.
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # UTC
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    # How many times it was shown: 1 = first time, 2 = re-prompt.
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    # When it was first shown. Re-prompt and "missed" timing count from here.
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # When it was marked taken or missed.
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    schedule: Mapped[MedicationSchedule] = relationship()
