"""Shared FastAPI dependencies for controllers."""

import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.model.entities import User

SessionDep = Annotated[Session, Depends(get_session)]


def get_current_user(
    session: SessionDep,
    x_user_id: Annotated[uuid.UUID | None, Header()] = None,
) -> User:
    """TEMPORARY stand-in until real auth lands (S2-03 / S2-04, Zohreh).

    With DEV_USER_HEADER=true in .env, the caller is whoever the `X-User-Id` header names.
    That trusts the client completely, so it is off by default and must never be enabled
    outside local development. When auth is done, replace this function's body with the
    real token check; every endpoint already depends on it, so nothing else changes.
    """
    if not settings.dev_user_header or x_user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    user = session.get(User, x_user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
