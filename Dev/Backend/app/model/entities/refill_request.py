"""PB-04 prescription refill requests sent to the (mock) pharmacy."""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdTimestampMixin, status_check

# plan §8 PB-04: requested -> in_progress -> ready
REFILL_STATUSES = ("requested", "in_progress", "ready")
OPEN_REFILL_STATUSES = ("requested", "in_progress")


class RefillRequest(IdTimestampMixin, Base):
    __tablename__ = "refill_requests"
    __table_args__ = (
        CheckConstraint(status_check("status", REFILL_STATUSES), name="status"),
        # One open request per medication: asking twice (or a double confirm) can't
        # send two refills to the pharmacy.
        Index(
            "uq_refill_requests_open_medication",
            "medication_id",
            unique=True,
            postgresql_where=text("status IN ('requested', 'in_progress')"),
        ),
        Index("ix_refill_requests_user_created", "user_id", "created_at"),
    )

    # Whose medicine (the older adult), and who asked (them, or a caregiver with consent).
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    medication_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("medications.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(20), default="requested")
    external_ref: Mapped[str | None] = mapped_column(String(100))  # id in the mock pharmacy
