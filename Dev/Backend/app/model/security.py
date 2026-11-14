"""Password hashing and tokens.

- Passwords: argon2 (slow on purpose, so stolen hashes are hard to crack).
- Access token: a short-lived JWT (15 min) with the user id and role.
- Refresh token: a long random string. We store only its SHA-256 hash.
"""

# hashlib: makes SHA-256 hashes. secrets: makes safe random strings.
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

# jwt (PyJWT): creates and checks access tokens.
import jwt

# PasswordHasher: argon2's tool for hashing and checking passwords.
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import settings

# HS256 = sign the token with our secret key (JWT_SECRET in .env).
JWT_ALGORITHM = "HS256"

# One shared hasher with argon2's safe default settings.
_password_hasher = PasswordHasher()


# ---------- Passwords ----------


def hash_password(plain_password: str) -> str:
    """Turn a password into a scrambled string we can save in users.password_hash.
    Each call adds a random 'salt', so the same password gives a different hash each time."""
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """True if the password matches the saved hash. Never raises, just returns False."""
    try:
        return _password_hasher.verify(password_hash, plain_password)
    except (VerificationError, InvalidHashError):
        # VerificationError: wrong password. InvalidHashError: the saved hash is broken.
        return False


# ---------- Access tokens (JWT) ----------


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    """Make a signed token the frontend sends with every request."""
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),  # "subject" = who this token belongs to (must be text)
        "role": role,  # used later for permission checks (S2-04)
        "iat": now,  # "issued at"
        "exp": now + timedelta(minutes=settings.access_token_minutes),  # "expires"
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Check the token and return its claims.
    Raises jwt.InvalidTokenError if it is fake, changed, or expired."""
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[JWT_ALGORITHM],  # only accept HS256 (blocks a known trick attack)
        options={"require": ["exp", "sub", "role"]},  # these claims must exist
    )


# ---------- Refresh tokens (used by the sessions table next) ----------


def new_refresh_token() -> str:
    """A long random string (about 43 characters). Impossible to guess."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """SHA-256 of a refresh token. We save this, never the real token.
    SHA-256 (fast) is OK here because the token is long and random.
    Passwords need argon2 (slow) because people choose weak passwords."""
    return hashlib.sha256(token.encode()).hexdigest()
