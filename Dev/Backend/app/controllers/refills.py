"""Prescription refill endpoint (PB-04, plan §10). Requesting a refill goes through
/actions, like every other state-changing operation (plan §5.3); this router reads the
requests back, with statuses refreshed from the pharmacy.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.controllers.dependencies import Db, Pharmacy, require_access
from app.model.entities import Medication
from app.model.services import refill_service
from app.views.schemas.refills import RefillOut

router = APIRouter(tags=["refills"])

CanRead = Annotated[uuid.UUID, Depends(require_access("medications:read"))]


@router.get("/older-adults/{older_adult_id}/refills", response_model=list[RefillOut])
def list_refills(older_adult_id: CanRead, db: Db, pharmacy: Pharmacy) -> list[RefillOut]:
    """This older adult's refill requests, newest first (not allowed -> 404)."""
    requests = refill_service.list_refills(db, older_adult_id, pharmacy)
    db.commit()  # save any progress the pharmacy reported
    return [RefillOut.from_entity(r, db.get(Medication, r.medication_id)) for r in requests]
