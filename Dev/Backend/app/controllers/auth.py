"""Auth endpoints. Business rules live in auth_service, not here."""

from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Response, status

from app.config import settings
from app.controllers.dependencies import Db
from app.model.services import auth_service
from app.model.services.auth_service import (
    EmailAlreadyRegistered,
    InvalidCredentials,
    InvalidRefreshToken,
)
from app.views.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])

# The browser sends this cookie ONLY to /api/v1/auth/..., not to every endpoint.
COOKIE_NAME = "refresh_token"
COOKIE_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,  # JavaScript can't read it, so a bad script can't steal it
        secure=settings.cookie_secure,
        samesite="lax",  # other websites can't make the browser send it
        path=COOKIE_PATH,
        max_age=settings.refresh_token_days * 24 * 60 * 60,  # in seconds
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=COOKIE_NAME,
        path=COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
def register(body: RegisterRequest, db: Db) -> UserResponse:
    """Create a caregiver account."""
    try:
        user = auth_service.register_caregiver(
            db, email=body.email, password=body.password, display_name=body.display_name
        )
    except EmailAlreadyRegistered:
        raise HTTPException(status.HTTP_409_CONFLICT, "This email is already registered.") from None
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, response: Response, db: Db) -> TokenResponse:
    """Email + password → access token (JSON) + refresh token (cookie)."""
    try:
        result = auth_service.login(
            db, email=body.email, password=body.password, device_label=body.device_label
        )
    except InvalidCredentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password.") from None
    _set_refresh_cookie(response, result.refresh_token)
    return TokenResponse(access_token=result.access_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    response: Response,
    db: Db,
    refresh_token: Annotated[str | None, Cookie()] = None,  # read from the cookie
) -> TokenResponse:
    """Cookie → new access token + new refresh cookie."""
    if refresh_token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in.")
    try:
        result = auth_service.refresh(db, refresh_token)
    except InvalidRefreshToken:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please sign in again.") from None
    _set_refresh_cookie(response, result.refresh_token)
    return TokenResponse(access_token=result.access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    db: Db,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> None:
    """End this device's session. Always succeeds."""
    if refresh_token is not None:
        auth_service.logout(db, refresh_token)
    _clear_refresh_cookie(response)
