"""User profile endpoints."""

from fastapi import APIRouter

from app.controllers.dependencies import CurrentUser
from app.views.schemas.auth import UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
def read_me(user: CurrentUser) -> UserResponse:
    """The signed-in user's own profile. CurrentUser = 401 if not signed in."""
    return UserResponse.model_validate(user)
