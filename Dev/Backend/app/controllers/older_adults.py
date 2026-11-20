"""Older adult profiles."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.controllers.dependencies import CurrentUser, Db
from app.model.entities import User
from app.model.services import older_adult_service
from app.model.services.consent_service import list_active_grants
from app.model.services.older_adult_service import NotACaregiver
from app.views.schemas.auth import UserResponse
from app.views.schemas.care import (
    ConsentGrantResponse,
    CreateOlderAdultRequest,
    OlderAdultCreatedResponse,
)

router = APIRouter(prefix="/older-adults", tags=["older adults"])


@router.get("", response_model=list[UserResponse])
def list_older_adults(user: CurrentUser, db: Db) -> list[UserResponse]:
    """Show caregivers the profiles they can manage and pair to a device."""
    if user.role != "caregiver":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only caregivers can do this.")
    ids = [
        grant.older_adult_id
        for grant in list_active_grants(db, user)
        if grant.caregiver_id == user.id and "profile:manage" in grant.scopes
    ]
    if not ids:
        return []
    adults = db.scalars(select(User).where(User.id.in_(ids)).order_by(User.display_name)).all()
    return [UserResponse.model_validate(adult) for adult in adults]


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
