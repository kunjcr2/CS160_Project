"""Users of the system (plan §5.1, §5.2, §9).

- Caregivers, support agents, and admins sign in with email + password.
- Older adults have NO email or password: they redeem a one-time pairing code
  on their device once, then stay signed in (sessions table, added next).
"""

# CheckConstraint: a rule the database checks every time a row is saved.
# Float: a column type for decimal numbers (like 1.0 or 0.8).
# String: a column type for text, with a maximum length.
from sqlalchemy import CheckConstraint, Float, String

# Mapped: says what Python type a column holds (and if it can be empty).
# mapped_column: describes the column in the database (type, default, unique, ...).
from sqlalchemy.orm import Mapped, mapped_column

# Base: the parent class every table inherits from (so Alembic can find it).
# IdTimestampMixin: adds id, created_at, and updated_at to the table automatically.
# status_check: helper that builds the rule "this column must be one of these words".
from .base import Base, IdTimestampMixin, status_check

# The only roles allowed. Kept in one place so code and tests can reuse it.
ROLES = ("older_adult", "caregiver", "support_agent", "admin")


class User(IdTimestampMixin, Base):
    """A person who uses the system: an older adult, caregiver, support agent, or admin."""
    # The table's name inside PostgreSQL.
    __tablename__ = "users"

    # Rules the DATABASE enforces, so a bug in Python can't save bad data.
    # Their full names come from the naming rule in base.py (e.g. "ck_users_role").
    __table_args__ = (
        # Rule 1: role must be one of the 4 words in ROLES.
        CheckConstraint(status_check("role", ROLES), name="role"),
        # Rule 2: everyone except older adults signs in with email + password,
        # so those two columns can only be empty for an older adult.
        CheckConstraint(
            "role = 'older_adult' OR (email IS NOT NULL AND password_hash IS NOT NULL)",
            name="login_needs_email_and_password",
        ),
        # Rule 3: speech speed must stay in a sensible range (1.0 = normal).
        CheckConstraint("speech_rate BETWEEN 0.5 AND 2.0", name="speech_rate_range"),
    )

    # --- Who they are and how they log in ---

    # One of ROLES. Mapped[str] means this column can NEVER be empty.
    role: Mapped[str] = mapped_column(String(20))

    # Login email. "str | None" means it CAN be empty (older adults have none).
    # unique=True: two accounts can't share one email.
    # The auth service saves it in lowercase, so "A@x.com" and "a@x.com" count as the same.
    email: Mapped[str | None] = mapped_column(String(254), unique=True)

    # The scrambled (argon2) version of the password, NEVER the real password.
    # Empty for older adults, who log in with a pairing code instead.
    password_hash: Mapped[str | None] = mapped_column(String(255))

    # --- Profile (plan §6.1) ---

    # Full name, e.g. "Margaret Lee". Required.
    display_name: Mapped[str] = mapped_column(String(120))

    # What the assistant calls them, e.g. "Maggie". Optional.
    preferred_name: Mapped[str | None] = mapped_column(String(60))

    # Language code. Only English ("en") for now; kept so we can add more later (plan §6.8).
    preferred_language: Mapped[str] = mapped_column(String(10), default="en")

    # Their local time zone. Reminders are calculated in this zone, then saved in UTC.
    timezone: Mapped[str] = mapped_column(String(64), default="America/Los_Angeles")

    # How fast the assistant talks. 1.0 = normal, 0.8 = slower, 1.2 = faster.
    speech_rate: Mapped[float] = mapped_column(Float, default=1.0)
