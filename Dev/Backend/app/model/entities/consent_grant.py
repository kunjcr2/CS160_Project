"""Consent grants: which caregiver may see which older adult's data,
and which parts of it (scopes)."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdTimestampMixin

# Parts of the data a caregiver can be allowed to see or manage.
# Conversation transcripts are NEVER a scope.
SCOPES = ("profile:manage", "appointments:read", "medications:read", "medications:manage")

# Builds: 'profile:manage', 'appointments:read', ...  (used in the rule below)
_ALLOWED = ", ".join(f"'{scope}'" for scope in SCOPES)


class ConsentGrant(IdTimestampMixin, Base):
    """Permission for one caregiver to access parts of one older adult's data."""

    __tablename__ = "consent_grants"
    __table_args__ = (
        # Rule 1: you can't give a grant to yourself.
        CheckConstraint("older_adult_id <> caregiver_id", name="not_self"),
        # Rule 2: a grant must allow at least one thing.
        CheckConstraint("cardinality(scopes) > 0", name="scopes_not_empty"),
        # Rule 3: every scope must be in SCOPES ("<@" means "is inside").
        CheckConstraint(f"scopes <@ ARRAY[{_ALLOWED}]::varchar[]", name="scopes_allowed"),
        # Rule 4: only ONE active grant per caregiver + older adult pair.
        # Revoked grants don't count (partial unique index, like appointments).
        Index(
            "uq_consent_grants_active_pair",
            "older_adult_id",
            "caregiver_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    # Whose data. If the older adult is deleted, their grants go too.
    older_adult_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    # Who may see it. index=True: makes "list my grants" fast for a caregiver.
    caregiver_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    # A PostgreSQL list of text, e.g. ["appointments:read", "medications:read"].
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String(40)))

    # Empty = active. Filled = taken back. (created_at = when it was granted.)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
