"""Auth service: register, login, refresh, logout.

Controllers call these functions. No HTTP code here: the controller turns
our errors into HTTP answers (401, 409, ...).
"""

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

# Renamed to DbSession because our model is also called "Session".
from sqlalchemy.orm import Session as DbSession

from app.config import settings
from app.model.entities import PairingCode, Session, User
from app.model.permissions import can_access
from app.model.security import (
    create_access_token,
    hash_pairing_code,
    hash_password,
    hash_token,
    new_refresh_token,
    verify_password,
)

# A random 8-digit code can, very rarely, collide with another caregiver's
# still-active code (the unique index covers every unused code, not just
# this older adult's). Retry a few times with a fresh code instead of 500ing.
_MAX_CODE_ATTEMPTS = 5

# ---------- Errors (the controller maps each one to an HTTP status) ----------


class AuthError(Exception):
    """Parent of every login problem."""


class EmailAlreadyRegistered(AuthError):
    """Someone already uses this email."""


class InvalidCredentials(AuthError):
    """Wrong email OR wrong password. We never say which (that would help attackers)."""


class InvalidRefreshToken(AuthError):
    """Refresh token is unknown, expired, or revoked."""


class NotAllowed(AuthError):
    """Not allowed, or the person doesn't exist (we don't say which)."""


class InvalidPairingCode(AuthError):
    """Code is unknown, expired, or already used."""


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
    """Swap a refresh token for a NEW access token and a NEW refresh token,
    on the SAME sessions row.

    "Rotation": the old refresh token stops working right away, so a stolen
    copy is useful only until the real device refreshes once. The row (and its
    device identity) stays put instead of being replaced, so a caregiver's
    revoke can't race a rotation and land on a row that's already gone. The
    row's `expires_at` is NOT extended either: a session has one fixed
    lifetime from login, however many times it rotates.
    """
    session = _find_session(db, refresh_token)
    if session is None or not session.is_active(_now()):
        raise InvalidRefreshToken()
    new_token = new_refresh_token()
    session.refresh_token_hash = hash_token(new_token)
    user = db.get(User, session.user_id)
    db.commit()
    return LoginResult(
        user=user,
        access_token=create_access_token(user.id, user.role),
        refresh_token=new_token,
    )


def logout(db: DbSession, refresh_token: str) -> None:
    """End this device's session. Calling it twice is fine (no error)."""
    current = _find_session(db, refresh_token)
    if current is not None and current.revoked_at is None:
        current.revoked_at = _now()
        db.commit()


def create_pairing_code(
    db: DbSession, *, actor: User, older_adult_id: uuid.UUID
) -> tuple[str, datetime]:
    """Make an 8-digit one-time code. Caregiver-only, and needs 'profile:manage'
    for this older adult."""
    if actor.role != "caregiver" or not can_access(db, actor, older_adult_id, "profile:manage"):
        raise NotAllowed()

    # A fresh code supersedes any of this caregiver's codes still outstanding
    # for this older adult, so a lost or forgotten one can't be redeemed later.
    _expire_unused_codes(db, older_adult_id=older_adult_id, created_by=actor.id)

    expires_at = _now() + timedelta(minutes=settings.pairing_code_minutes)
    for attempt in range(_MAX_CODE_ATTEMPTS):
        code = _new_code()
        try:
            # Savepoint: if this insert collides, undo ONLY this insert.
            # A full db.rollback() would also undo _expire_unused_codes above,
            # and the caregiver's older codes would work again.
            with db.begin_nested():
                db.add(
                    PairingCode(
                        code_hash=hash_pairing_code(code),  # save the hash, never the code
                        older_adult_id=older_adult_id,
                        created_by=actor.id,
                        expires_at=expires_at,
                    )
                )
        except IntegrityError:
            if attempt == _MAX_CODE_ATTEMPTS - 1:
                db.rollback()
                raise
            continue
        db.commit()  # saves the expiry of old codes + the new code together
        return code, expires_at


def redeem_pairing_code(
    db: DbSession, *, code: str, device_label: str | None = None
) -> LoginResult:
    """Older adult's device types the code ONCE → signed in."""
    digits = "".join(ch for ch in code if ch.isdigit())  # "1234 5678" → "12345678"
    pairing = db.scalar(
        select(PairingCode)
        .where(PairingCode.code_hash == hash_pairing_code(digits))
        .with_for_update()  # lock: two devices can't use the same code at once
    )
    if pairing is None or not pairing.is_usable(_now()):
        raise InvalidPairingCode()
    creator = db.get(User, pairing.created_by)
    # The creator's access may have been revoked after the code was minted;
    # re-check it now so a code made before a revoke can't still sign in.
    if creator is None or not can_access(db, creator, pairing.older_adult_id, "profile:manage"):
        raise InvalidPairingCode()
    pairing.used_at = _now()  # now it can never be used again
    user = db.get(User, pairing.older_adult_id)
    return _start_session(db, user, device_label)  # saves used_at + session together


# ---------- Private helpers (start with "_": only used in this file) ----------


def _new_code() -> str:
    """A random 8-digit code. Digits only: easier for an older adult to type.
    (A separate function so tests can force a collision.)"""
    return "".join(secrets.choice("0123456789") for _ in range(8))


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


def _expire_unused_codes(
    db: DbSession, *, older_adult_id: uuid.UUID, created_by: uuid.UUID
) -> None:
    """Make this caregiver's still-usable codes for this older adult stop working."""
    now = _now()
    db.execute(
        update(PairingCode)
        .where(
            PairingCode.older_adult_id == older_adult_id,
            PairingCode.created_by == created_by,
            PairingCode.used_at.is_(None),
            PairingCode.expires_at > now,
        )
        .values(expires_at=now)
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
