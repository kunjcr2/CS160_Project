"""Older adult profiles."""

from fastapi import APIRouter, HTTPException, status

from app.controllers.dependencies import CurrentUser, Db
from app.model.services import older_adult_service
from app.model.services.older_adult_service import NotACaregiver
from app.views.schemas.auth import UserResponse
from app.views.schemas.care import (
    ConsentGrantResponse,
    CreateOlderAdultRequest,
    OlderAdultCreatedResponse,
)

router = APIRouter(prefix="/older-adults", tags=["older adults"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=OlderAdultCreatedResponse)
def create_older_adult(
    body: CreateOlderAdultRequest, user: CurrentUser, db: Db
) -> OlderAdultCreatedResponse:
    try:
        older_adult, grant = older_adult_service.create_older_adult(
            db,
            caregiver=user,
            display_name=body.display_name,
            preferred_name=body.preferred_name,
            timezone=body.timezone,
            scopes=body.scopes,
        )
    except NotACaregiver:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only caregivers can do this.") from None
    return OlderAdultCreatedResponse(
        older_adult=UserResponse.model_validate(older_adult),
        grant=ConsentGrantResponse.model_validate(grant),
    )
