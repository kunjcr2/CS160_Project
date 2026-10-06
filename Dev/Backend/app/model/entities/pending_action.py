"""Persisted Commands awaiting confirmation (plan §4, §5.3). Booking needs this."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdTimestampMixin, status_check

ACTION_STATUSES = ("proposed", "confirmed", "executed", "failed", "cancelled", "expired", "undone")


class PendingAction(IdTimestampMixin, Base):
    __tablename__ = "pending_actions"
    __table_args__ = (
        CheckConstraint(status_check("status", ACTION_STATUSES), name="status"),
        # Plan rule "one pending action per user at a time", enforced by the database.
        Index(
            "uq_pending_actions_one_proposed_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'proposed'"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    action_type: Mapped[str] = mapped_column(String(40))  # e.g. "book_appointment" → Command class
    payload: Mapped[dict] = mapped_column(JSONB)  # Command arguments, e.g. {"slot_id": ...}
    summary_text: Mapped[str] = mapped_column(Text)  # what was read back to the user
    status: Mapped[str] = mapped_column(String(20), default="proposed")
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict | None] = mapped_column(JSONB)  # e.g. {"appointment_id": ...}
