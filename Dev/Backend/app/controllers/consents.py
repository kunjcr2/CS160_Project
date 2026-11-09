"""Consent grants."""

import uuid

from fastapi import APIRouter, HTTPException, status

from app.controllers.dependencies import CurrentUser, Db
from app.model.services import consent_service
from app.model.services.consent_service import GrantNotFound
from app.views.schemas.care import ConsentGrantResponse

router = APIRouter(prefix="/consents", tags=["consents"])


@router.get("", response_model=list[ConsentGrantResponse])
def list_consents(user: CurrentUser, db: Db) -> list[ConsentGrantResponse]:
    grants = consent_service.list_active_grants(db, user)
    return [ConsentGrantResponse.model_validate(grant) for grant in grants]


@router.delete("/{grant_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_consent(grant_id: uuid.UUID, user: CurrentUser, db: Db) -> None:
    try:
        consent_service.revoke_grant(db, user, grant_id)
    except GrantNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.") from None
