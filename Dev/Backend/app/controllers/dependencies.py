"""Shared FastAPI dependencies."""

import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session as DbSession

from app.adapters.healthcare.interface import HealthcareProvider
from app.db import get_session
from app.model.entities import User
from app.model.permissions import can_access
from app.model.security import decode_access_token

# Reads the "Authorization: Bearer <token>" header. auto_error=False: we send our own 401.
_bearer = HTTPBearer(auto_error=False)

# Short names to use in endpoints:  def my_endpoint(db: Db, user: CurrentUser)
Db = Annotated[DbSession, Depends(get_session)]


def _not_signed_in() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not signed in.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Db,
) -> User:
    """Return the signed-in user, or stop the request with 401."""
    if credentials is None:  # no token sent
        raise _not_signed_in()
    try:
        claims = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError):  # fake, expired, or broken token
        raise _not_signed_in() from None
    user = db.get(User, user_id)
    if user is None:  # token is fine but the user was deleted
        raise _not_signed_in()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_access(scope: str):
    """For routes with {older_adult_id} in the path. Not allowed → 404.

    404, not 403: we don't even admit that the data exists (plan §5.2).
    Usage:
        owner_id: Annotated[uuid.UUID, Depends(require_access("appointments:read"))]
    """

    def check(older_adult_id: uuid.UUID, user: CurrentUser, db: Db) -> uuid.UUID:
        if not can_access(db, user, older_adult_id, scope):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
        return older_adult_id

    return check


def get_healthcare(request: Request) -> HealthcareProvider:
    """The one shared doctor's office, built when the app starts (main.py)."""
    return request.app.state.healthcare


# Usage:  def my_endpoint(office: Healthcare)
# Tests can swap it:  app.dependency_overrides[get_healthcare] = lambda: MockHealthcareProvider(...)
Healthcare = Annotated[HealthcareProvider, Depends(get_healthcare)]
