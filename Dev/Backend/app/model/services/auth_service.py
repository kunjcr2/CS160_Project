"""Auth service: register, login, refresh, logout.

Controllers call these functions. No HTTP code here: the controller turns
our errors into HTTP answers (401, 409, ...).
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

# Renamed to DbSession because our model is also called "Session".
from sqlalchemy.orm import Session as DbSession

from app.config import settings
from app.model.entities import Session, User
from app.model.security import (
    create_access_token,
    hash_password,
    hash_token,
    new_refresh_token,
    verify_password,
)

# ---------- Errors (the controller maps each one to an HTTP status) ----------


class AuthError(Exception):
    """Parent of every login problem."""


class EmailAlreadyRegistered(AuthError):
    """Someone already uses this email."""


class InvalidCredentials(AuthError):
    """Wrong email OR wrong password. We never say which (that would help attackers)."""


class InvalidRefreshToken(AuthError):
    """Refresh token is unknown, expired, or revoked."""


# ---------- Result ----------


@dataclass
class LoginResult:
    """What a successful login or refresh gives back."""

    user: User
    access_token: str  # short JWT, sent with every request
    refresh_token: str  # long random string; goes in a cookie, NEVER in the database


# A fake hash, used when the email doesn't exist. Checking against it takes the
# same time as a real check, so attackers can't tell "no such email" by timing.
_DUMMY_HASH = hash_password("dummy-password-for-timing")


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize_email(email: str) -> str:
    """'  Ana@X.com ' → 'ana@x.com', so the same email always looks the same."""
    return email.strip().lower()


# ---------- Public functions ----------
# The "*" means every argument after it must be named, e.g. email="...".
# This prevents mixing up email and password by accident.


def register_caregiver(db: DbSession, *, email: str, password: str, display_name: str) -> User:
    """Create a caregiver account."""
    user = User(
        role="caregiver",
        email=_normalize_email(email),
        password_hash=hash_password(password),
        display_name=display_name,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # The database's unique rule on email said no. We let the DATABASE check,
        # because two sign-ups at the same moment could both pass a Python check.
        db.rollback()
        raise EmailAlreadyRegistered() from None
    return user


def login(
    db: DbSession, *, email: str, password: str, device_label: str | None = None
) -> LoginResult:
    """Check email + password, then start a new session."""
    user = db.scalar(select(User).where(User.email == _normalize_email(email)))
    if user is None or user.password_hash is None:
        verify_password(password, _DUMMY_HASH)  # waste the same time on purpose
        raise InvalidCredentials()
    if not verify_password(password, user.password_hash):
        raise InvalidCredentials()
    return _start_session(db, user, device_label)


def refresh(db: DbSession, refresh_token: str) -> LoginResult:
    """Swap a refresh token for a NEW access token and a NEW refresh token.

    "Rotation": the old refresh token stops working right away, so a stolen
    copy is useful only until the real device refreshes once.
    """
    old = _find_session(db, refresh_token)
    if old is None or not old.is_active(_now()):
        raise InvalidRefreshToken()
    old.revoked_at = _now()
    user = db.get(User, old.user_id)
    return _start_session(db, user, old.device_label)  # saves both changes together


def logout(db: DbSession, refresh_token: str) -> None:
    """End this device's session. Calling it twice is fine (no error)."""
    current = _find_session(db, refresh_token)
    if current is not None and current.revoked_at is None:
        current.revoked_at = _now()
        db.commit()


# ---------- Private helpers (start with "_": only used in this file) ----------


def _start_session(db: DbSession, user: User, device_label: str | None) -> LoginResult:
    """Save a new session row and make both tokens."""
    refresh_token = new_refresh_token()
    db.add(
        Session(
            user_id=user.id,
            refresh_token_hash=hash_token(refresh_token),  # save the hash, not the token
            device_label=device_label,
            expires_at=_now() + timedelta(days=settings.refresh_token_days),
        )
    )
    db.commit()
    return LoginResult(
        user=user,
        access_token=create_access_token(user.id, user.role),
        refresh_token=refresh_token,
    )


def _find_session(db: DbSession, refresh_token: str) -> Session | None:
    """Find the session for this token. with_for_update() LOCKS the row,
    so two refreshes at the same moment can't both use the same token."""
    query = (
        select(Session)
        .where(Session.refresh_token_hash == hash_token(refresh_token))
        .with_for_update()
    )
    return db.scalar(query)
