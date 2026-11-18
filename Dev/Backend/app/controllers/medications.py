"""Medication endpoints (PB-03).

Viewing and adding go through the older adult's id, so the same consent rules apply
as everywhere else (require_access; not allowed -> 404):
- the older adult themself can do everything with their own medications;
- a caregiver needs "medications:read" to view and "medications:manage" to add.

Answering a reminder (taken / missed) is ONLY for the person who takes the medicine.
"""

import uuid
from datetime import UTC, date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.controllers.dependencies import CurrentUser, Db, require_access
from app.model.entities import MedicationReminder, User
from app.model.services import medication_reminders, medication_service
from app.model.services.medication_reminders import (
    ReminderNotChangeableError,
    ReminderNotFoundError,
)
from app.views import messages
from app.views.schemas.medications import (
    CreateMedicationRequest,
    MedicationReminderResponse,
    MedicationResponse,
)

router = APIRouter(tags=["medications"])

CanRead = Annotated[uuid.UUID, Depends(require_access("medications:read"))]
CanManage = Annotated[uuid.UUID, Depends(require_access("medications:manage"))]


def _now() -> datetime:
    return datetime.now(UTC)


# ---------- Medications ----------


@router.get("/older-adults/{older_adult_id}/medications", response_model=list[MedicationResponse])
def list_medications(older_adult_id: CanRead, db: Db) -> list[MedicationResponse]:
    return [
        MedicationResponse.model_validate(medication)
        for medication in medication_service.list_medications(db, older_adult_id)
    ]


@router.post(
    "/older-adults/{older_adult_id}/medications",
    status_code=status.HTTP_201_CREATED,
    response_model=MedicationResponse,
)
def create_medication(
    older_adult_id: CanManage, body: CreateMedicationRequest, db: Db
) -> MedicationResponse:
    """Add a medication and its times. Doses for the next days are created right away."""
    medication = medication_service.create_medication(
        db,
        older_adult_id,
        name=body.name,
        dosage=body.dosage,
        instructions=body.instructions,
        refills_remaining=body.refills_remaining,
        schedules=[(s.time_of_day, s.days_of_week) for s in body.schedules],
        now=_now(),
    )
    db.commit()
    return MedicationResponse.model_validate(medication)


# ---------- One day's doses ----------


@router.get(
    "/older-adults/{older_adult_id}/medication-reminders",
    response_model=list[MedicationReminderResponse],
)
def list_doses(
    older_adult_id: CanRead,
    db: Db,
    day: Annotated[
        date | None, Query(alias="date", description="Local date; default today")
    ] = None,
) -> list[MedicationReminderResponse]:
    """Every dose on one day, in the older adult's local time zone, earliest first."""
    if day is None:
        tz = ZoneInfo(db.get(User, older_adult_id).timezone)
        day = _now().astimezone(tz).date()  # "today" where the older adult lives
    return [
        _dose_response(reminder, medication.name, medication.dosage, medication.id)
        for reminder, medication in medication_service.doses_for_day(db, older_adult_id, day)
    ]


# ---------- Answering a reminder ----------


@router.post("/medication-reminders/{reminder_id}/taken", response_model=MedicationReminderResponse)
def mark_taken(reminder_id: uuid.UUID, user: CurrentUser, db: Db) -> MedicationReminderResponse:
    """I took it. Safe to call twice. 404: not found or not yours. 409: can't change now."""
    return _answer(medication_reminders.mark_taken, reminder_id, user, db)


@router.post(
    "/medication-reminders/{reminder_id}/missed", response_model=MedicationReminderResponse
)
def mark_missed(reminder_id: uuid.UUID, user: CurrentUser, db: Db) -> MedicationReminderResponse:
    """I skipped it. Safe to call twice. 404: not found or not yours. 409: can't change now."""
    return _answer(medication_reminders.mark_missed, reminder_id, user, db)


def _answer(action, reminder_id: uuid.UUID, user: User, db: Db) -> MedicationReminderResponse:
    """Run mark_taken or mark_missed and turn its errors into HTTP answers."""
    try:
        reminder = action(db, reminder_id, user, _now())
    except ReminderNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.") from None
    except ReminderNotChangeableError as error:
        message = (
            messages.MEDICATION_TOO_EARLY
            if error.code == "too_early"
            else messages.MEDICATION_NOT_CHANGEABLE
        )
        raise HTTPException(
            status.HTTP_409_CONFLICT, {"code": error.code, "message": message}
        ) from None
    db.commit()
    medication = reminder.schedule.medication
    return _dose_response(reminder, medication.name, medication.dosage, medication.id)


def _dose_response(
    reminder: MedicationReminder, name: str, dosage: str, medication_id: uuid.UUID
) -> MedicationReminderResponse:
    return MedicationReminderResponse(
        id=reminder.id,
        medication_id=medication_id,
        medication_name=name,
        dosage=dosage,
        due_at=reminder.due_at,
        status=reminder.status,
        attempts=reminder.attempts,
        confirmed_at=reminder.confirmed_at,
    )
