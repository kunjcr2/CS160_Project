"""One-time pairing codes.

A caregiver creates a short code. The older adult's device types it in ONCE,
gets a session, and stays signed in. Codes expire quickly and work only once.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdTimestampMixin


class PairingCode(IdTimestampMixin, Base):
    """A one-time code that signs in an older adult's device."""

    __tablename__ = "pairing_codes"

    # SHA-256 of the code. We never save the real code.
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)

    # The older adult who will be signed in by this code.
    older_adult_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    # The caregiver who created the code.
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    # Short life (about 15 minutes), so a lost code is soon useless.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Empty = not used yet. Filled = already used, can't be used again.
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def is_usable(self, now: datetime) -> bool:
        """True if the code was never used and has not expired."""
        return self.used_at is None and self.expires_at > now
