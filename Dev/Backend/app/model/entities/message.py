"""PB-07 care-team messages: send only (replies and read status deferred, plan §17)."""

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdTimestampMixin, status_check

MESSAGE_STATUSES = ("sent", "failed")
MESSAGE_BODY_MAX_LENGTH = 2000


class Message(IdTimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(status_check("status", MESSAGE_STATUSES), name="status"),
        Index("ix_messages_older_adult_created", "older_adult_id", "created_at"),
    )

    sender_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    older_adult_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("providers.id"))
    body: Mapped[str] = mapped_column(String(MESSAGE_BODY_MAX_LENGTH))
    status: Mapped[str] = mapped_column(String(20), default="sent")
    external_ref: Mapped[str | None] = mapped_column(String(100))  # id in the mock messaging system
