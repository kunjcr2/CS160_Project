"""JSON shape for prescription refill requests (PB-04)."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.model.entities import Medication, RefillRequest
from app.views import messages


class RefillMedicationOut(BaseModel):
    id: uuid.UUID
    name: str
    dosage: str
    refills_remaining: int


class RefillOut(BaseModel):
    id: uuid.UUID
    medication: RefillMedicationOut
    status: str  # requested, in_progress, ready
    status_message: str  # the sentence to show or speak, e.g. "Your Lisinopril is ready..."
    created_at: datetime

    @classmethod
    def from_entity(cls, request: RefillRequest, medication: Medication) -> "RefillOut":
        return cls(
            id=request.id,
            medication=RefillMedicationOut.model_validate(medication, from_attributes=True),
            status=request.status,
            status_message=messages.REFILL_STATUS[request.status].format(name=medication.name),
            created_at=request.created_at,
        )
