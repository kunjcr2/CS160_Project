"""Signed-in devices. One row per login.

The device keeps a long random refresh token. We save only its SHA-256 hash,
so a stolen database can't be used to sign in. Logout = set revoked_at.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdTimestampMixin


class Session(IdTimestampMixin, Base):
    """One signed-in device for one user."""

    __tablename__ = "sessions"

    # Who is signed in. If the user is deleted, their sessions are deleted too.
    # index=True: makes "find all sessions of this user" fast (for "log out everywhere").
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # SHA-256 of the refresh token (64 characters). Unique so we can look it up.
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True)

    # A friendly name, e.g. "Margaret's iPad". Helps a caregiver revoke a lost device.
    device_label: Mapped[str | None] = mapped_column(String(100))

    # After this time the refresh token stops working.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Empty = still active. Filled = logged out or revoked.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def is_active(self, now: datetime) -> bool:
        """True if this session can still be used."""
        return self.revoked_at is None and self.expires_at > now
