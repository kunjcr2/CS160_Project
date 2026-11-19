"""PB-06 human assistance: a "request help" record shown in a support queue (the simple
version from the plan §17 cut order; no live call or chat)."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdTimestampMixin, status_check

# open -> in_progress (an agent took it) -> resolved; an agent can also resolve it directly.
ASSISTANCE_STATUSES = ("open", "in_progress", "resolved")
OPEN_ASSISTANCE_STATUSES = ("open", "in_progress")
# Why help was asked for: the user asked, or the assistant kept failing (plan §7).
ASSISTANCE_REASONS = ("user_request", "repeated_failures")
ASSISTANCE_SUMMARY_MAX_LENGTH = 300


class AssistanceRequest(IdTimestampMixin, Base):
    __tablename__ = "assistance_requests"
    __table_args__ = (
        CheckConstraint(status_check("status", ASSISTANCE_STATUSES), name="status"),
        CheckConstraint(status_check("reason", ASSISTANCE_REASONS), name="reason"),
        # resolved always has a time; open and in_progress never do.
        CheckConstraint(
            "(status = 'resolved') = (resolved_at IS NOT NULL)", name="resolved_at_matches_status"
        ),
        # One unresolved request per older adult: asking again doesn't queue duplicates.
        Index(
            "uq_assistance_requests_open_user",
            "user_id",
            unique=True,
            postgresql_where=text("status IN ('open', 'in_progress')"),
        ),
        # The queue: unresolved requests, oldest first.
        Index(
            "ix_assistance_requests_queue",
            "created_at",
            postgresql_where=text("status IN ('open', 'in_progress')"),
        ),
    )

    # Who needs help (the older adult), and who asked (them, or a caregiver with consent).
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    reason: Mapped[str] = mapped_column(String(20), default="user_request")
    # A short, consented summary of what they were trying to do: never the transcript.
    summary: Mapped[str | None] = mapped_column(String(ASSISTANCE_SUMMARY_MAX_LENGTH))
    status: Mapped[str] = mapped_column(String(20), default="open")
    # The support agent handling it. SET NULL: removing an agent keeps the request.
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
