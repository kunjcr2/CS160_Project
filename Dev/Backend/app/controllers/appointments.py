"""PB-01 read endpoints (plan §10). Booking goes through /actions (confirmation)."""

import uuid
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.adapters.healthcare.interface import ProviderUnavailableError
from app.controllers.dependencies import CurrentUser, Db, Healthcare
from app.model.entities import Provider
from app.model.services.appointment_service import MAX_OPTIONS, AppointmentService
from app.views import messages
from app.views.schemas.appointments import AppointmentOut, ProviderOut, SlotOut

router = APIRouter(tags=["appointments"])

# The doctor's office answers at most 60 days per search; stay inside that.
MAX_RANGE = timedelta(days=31)


@router.get("/providers", response_model=list[ProviderOut])
def list_providers(
    user: CurrentUser,
    session: Db,
    office: Healthcare,
    name: Annotated[str | None, Query(description='e.g. "Dr. Chen"')] = None,
):
    providers = AppointmentService(session, healthcare=office).find_providers(name)
    return [ProviderOut.from_entity(p) for p in providers]


@router.get("/slots", response_model=list[SlotOut])
def list_slots(
    provider_id: uuid.UUID,
    user: CurrentUser,
    session: Db,
    office: Healthcare,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=20)] = MAX_OPTIONS,
):
    """Free slots between two dates (inclusive, in the user's time zone). Defaults to the
    next 7 days. Returns at most `limit` slots, earliest first."""
    provider = session.get(Provider, provider_id)
    if provider is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Provider not found")
    service = AppointmentService(session, healthcare=office)
    start = date_from or service.clock().date()
    end = date_to or start + timedelta(days=7)
    if end - start > MAX_RANGE:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Search at most {MAX_RANGE.days} days at a time.",
        )
    try:
        options = service.find_slots(user, provider, start, end, limit=limit)
    except ProviderUnavailableError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            {"code": "provider_unavailable", "message": messages.SERVICE_UNAVAILABLE},
        ) from None
    return [SlotOut.from_option(option, user) for option in options]


@router.get("/appointments", response_model=list[AppointmentOut])
def list_appointments(user: CurrentUser, session: Db, office: Healthcare):
    """The user's upcoming booked appointments, earliest first."""
    appointments = AppointmentService(session, healthcare=office).upcoming(user)
    return [_out(session, a, user) for a in appointments]


@router.get("/appointments/{appointment_id}", response_model=AppointmentOut)
def get_appointment(appointment_id: uuid.UUID, user: CurrentUser, session: Db, office: Healthcare):
    appointment = AppointmentService(session, healthcare=office).get(user, appointment_id)
    if appointment is None:  # also when it belongs to someone else
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found")
    return _out(session, appointment, user)


def _out(session, appointment, user) -> AppointmentOut:
    provider = session.get(Provider, appointment.provider_id)
    return AppointmentOut.from_entity(appointment, provider, user)
