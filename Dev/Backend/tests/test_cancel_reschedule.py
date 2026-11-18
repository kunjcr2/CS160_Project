"""PB-01 cancel and reschedule (S4-13): both need a yes, both update the mock office, and
reminders follow (PB-02): a cancelled appointment gets none, a moved one gets new ones."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from conftest import next_tuesday
from sqlalchemy import select

from app.adapters.healthcare.interface import ProviderUnavailableError
from app.model.entities import Appointment, AppointmentReminder, Provider
from app.model.services.action_service import ActionService
from app.model.services.appointment_service import AppointmentService
from app.model.subscribers.reminder_scheduler import reminder_times
from app.views import messages
from app.views.formatting import spoken_date, spoken_date_time, spoken_time

LA = "America/Los_Angeles"


@pytest.fixture(autouse=True)
def _fresh_provider(mock_provider):
    """Every test gets its own mock office (see conftest)."""


@pytest.fixture
def margaret(make_user):
    return make_user("Margaret")


def _slots(db, user, provider, office):
    """Next Tuesday's slots from 10 AM on (late enough for all three reminders)."""
    slots = AppointmentService(db, healthcare=office).find_slots(
        user, provider, next_tuesday(), next_tuesday(), limit=20
    )
    return [s for s in slots if s.starts_at.astimezone(ZoneInfo(LA)).hour >= 10]


def _book(db, user, provider, office, slot=None) -> Appointment:
    slot = slot or _slots(db, user, provider, office)[0]
    actions = ActionService(db, healthcare=office)
    outcome = actions.confirm(
        actions.propose(user, "book_appointment", {"slot_id": slot.slot_id}).id, user
    )
    db.commit()
    return db.get(Appointment, outcome.action.result["data"]["appointment_id"])


def _propose(client, action_type, **payload):
    return client.post("/api/v1/actions", json={"action_type": action_type, "payload": payload})


def _confirm(client, proposed):
    return client.post(f"/api/v1/actions/{proposed.json()['id']}/confirm")


def _reminders(db, appointment_id) -> dict[str, str]:
    rows = db.scalars(
        select(AppointmentReminder).where(AppointmentReminder.appointment_id == appointment_id)
    )
    return {row.kind: row.status for row in rows}


def _office_has(office, appointment) -> bool:
    return appointment.external_ref in office._bookings


# --- Cancel -----------------------------------------------------------------------------


def test_cancel_after_a_yes_frees_the_slot_and_stops_reminders(
    client, db, margaret, chen, mock_provider
):
    appointment = _book(db, margaret, chen, mock_provider)
    assert set(_reminders(db, appointment.id).values()) == {"scheduled"}
    client.login_as(margaret)

    proposed = _propose(client, "cancel_appointment", appointment_id=str(appointment.id))

    when = appointment.starts_at
    assert proposed.status_code == 201
    assert proposed.json()["summary_text"] == messages.CANCEL_CONFIRM.format(
        doctor="Dr. Lisa Chen", date=spoken_date(when, LA), time=spoken_time(when, LA)
    )
    db.refresh(appointment)
    assert appointment.status == "booked"  # nothing changes before the yes

    confirmed = _confirm(client, proposed)

    assert confirmed.json()["action"]["status"] == "executed"
    assert confirmed.json()["message"] == messages.CANCEL_DONE.format(
        doctor="Dr. Lisa Chen", date=spoken_date(when, LA), time=spoken_time(when, LA)
    )
    db.refresh(appointment)
    assert appointment.status == "cancelled"
    assert not _office_has(mock_provider, appointment)
    assert set(_reminders(db, appointment.id).values()) == {"cancelled"}
    assert client.get("/api/v1/appointments").json() == []
    # The slot is free again for anyone.
    free = [s.starts_at for s in _slots(db, margaret, chen, mock_provider)]
    assert appointment.starts_at in free


def test_saying_no_keeps_the_appointment(client, db, margaret, chen, mock_provider):
    appointment = _book(db, margaret, chen, mock_provider)
    client.login_as(margaret)
    proposed = _propose(client, "cancel_appointment", appointment_id=str(appointment.id))

    client.post(f"/api/v1/actions/{proposed.json()['id']}/cancel")

    db.refresh(appointment)
    assert appointment.status == "booked"
    assert _office_has(mock_provider, appointment)


def test_cannot_cancel_someone_elses_appointment(
    client, db, make_user, margaret, chen, mock_provider
):
    appointment = _book(db, margaret, chen, mock_provider)
    client.login_as(make_user("David"))

    response = _propose(client, "cancel_appointment", appointment_id=str(appointment.id))

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "appointment_not_found"  # same as missing


def test_cannot_cancel_twice(client, db, margaret, chen, mock_provider):
    appointment = _book(db, margaret, chen, mock_provider)
    client.login_as(margaret)
    _confirm(client, _propose(client, "cancel_appointment", appointment_id=str(appointment.id)))

    again = _propose(client, "cancel_appointment", appointment_id=str(appointment.id))

    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "not_changeable"


def test_cannot_cancel_a_past_appointment(client, db, margaret, chen, mock_provider):
    appointment = _book(db, margaret, chen, mock_provider)
    appointment.starts_at = datetime(2020, 1, 7, 18, 0, tzinfo=UTC)
    appointment.ends_at = datetime(2020, 1, 7, 18, 30, tzinfo=UTC)
    db.commit()
    client.login_as(margaret)

    response = _propose(client, "cancel_appointment", appointment_id=str(appointment.id))

    assert response.json()["detail"]["code"] == "not_changeable"


def test_office_down_on_cancel_changes_nothing(
    client, db, margaret, chen, mock_provider, monkeypatch
):
    appointment = _book(db, margaret, chen, mock_provider)
    client.login_as(margaret)
    proposed = _propose(client, "cancel_appointment", appointment_id=str(appointment.id))

    def office_down(ref):
        raise ProviderUnavailableError("down")

    monkeypatch.setattr(mock_provider, "cancel", office_down)
    confirmed = _confirm(client, proposed)

    assert confirmed.json()["action"]["status"] == "failed"
    assert confirmed.json()["message"] == messages.CANCEL_FAILED.format(phone=chen.phone)
    db.refresh(appointment)
    assert appointment.status == "booked"
    assert set(_reminders(db, appointment.id).values()) == {"scheduled"}


# --- Reschedule -------------------------------------------------------------------------


def test_reschedule_after_a_yes_moves_the_appointment_and_its_reminders(
    client, db, margaret, chen, mock_provider
):
    old = _book(db, margaret, chen, mock_provider)
    new_slot = _slots(db, margaret, chen, mock_provider)[1]
    client.login_as(margaret)

    proposed = _propose(
        client, "reschedule_appointment", appointment_id=str(old.id), slot_id=new_slot.slot_id
    )

    assert proposed.status_code == 201
    assert proposed.json()["summary_text"] == messages.RESCHEDULE_CONFIRM.format(
        doctor="Dr. Lisa Chen",
        old=spoken_date_time(old.starts_at, LA),
        new=spoken_date_time(new_slot.starts_at, LA),
        location="Valley Medical, Building B",
    )

    confirmed = _confirm(client, proposed)

    assert confirmed.json()["action"]["status"] == "executed"
    assert confirmed.json()["message"] == messages.RESCHEDULE_DONE.format(
        doctor="Dr. Lisa Chen",
        date=spoken_date(new_slot.starts_at, LA),
        time=spoken_time(new_slot.starts_at, LA),
    )
    result = confirmed.json()["action"]["result"]
    assert result["previous_appointment_id"] == str(old.id)
    new = db.get(Appointment, result["appointment_id"])
    db.refresh(old)
    assert (old.status, new.status) == ("cancelled", "booked")
    assert new.starts_at == new_slot.starts_at
    assert not _office_has(mock_provider, old)
    assert _office_has(mock_provider, new)
    # Reminders: the old time's stop, the new time gets its own at the right local times.
    assert set(_reminders(db, old.id).values()) == {"cancelled"}
    new_reminders = db.scalars(
        select(AppointmentReminder).where(AppointmentReminder.appointment_id == new.id)
    )
    assert {r.kind: r.due_at for r in new_reminders} == reminder_times(new.starts_at, LA)
    assert [a["id"] for a in client.get("/api/v1/appointments").json()] == [str(new.id)]


def test_reschedule_to_a_different_doctor_is_refused(client, db, margaret, chen, mock_provider):
    old = _book(db, margaret, chen, mock_provider)
    physio = Provider(
        name="Dr. Sam Patel",
        specialty="Physical therapy",
        location="Valley Medical, Building A",
        external_ref="mock-prac-physical-therapy-1",
    )
    db.add(physio)
    db.commit()
    other_slot = _slots(db, margaret, physio, mock_provider)[0]
    client.login_as(margaret)

    response = _propose(
        client, "reschedule_appointment", appointment_id=str(old.id), slot_id=other_slot.slot_id
    )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "different_doctor",
        "message": messages.RESCHEDULE_OTHER_DOCTOR,
    }


def test_reschedule_into_a_taken_slot_keeps_the_old_appointment(
    client, db, make_user, margaret, chen, mock_provider
):
    old = _book(db, margaret, chen, mock_provider)
    target = _slots(db, margaret, chen, mock_provider)[0]
    client.login_as(margaret)
    proposed = _propose(
        client, "reschedule_appointment", appointment_id=str(old.id), slot_id=target.slot_id
    )
    _book(db, make_user("David"), chen, mock_provider, slot=target)  # David gets there first

    confirmed = _confirm(client, proposed)

    assert confirmed.json()["action"]["status"] == "failed"
    assert confirmed.json()["action"]["result"] is None
    assert confirmed.json()["message"].startswith("Sorry, that time was just taken.")
    db.refresh(old)
    assert old.status == "booked"
    assert _office_has(mock_provider, old)
    assert set(_reminders(db, old.id).values()) == {"scheduled"}


def test_office_down_while_releasing_the_old_time_changes_nothing(
    client, db, margaret, chen, mock_provider, monkeypatch
):
    old = _book(db, margaret, chen, mock_provider)
    new_slot = _slots(db, margaret, chen, mock_provider)[1]
    client.login_as(margaret)
    proposed = _propose(
        client, "reschedule_appointment", appointment_id=str(old.id), slot_id=new_slot.slot_id
    )
    real_cancel = mock_provider.cancel

    def cancel(ref):
        if ref == old.external_ref:  # the office fails to release the OLD booking
            raise ProviderUnavailableError("down")
        real_cancel(ref)

    monkeypatch.setattr(mock_provider, "cancel", cancel)
    confirmed = _confirm(client, proposed)

    assert confirmed.json()["action"]["status"] == "failed"
    assert confirmed.json()["message"] == messages.RESCHEDULE_FAILED.format(phone=chen.phone)
    db.refresh(old)
    assert old.status == "booked"
    assert db.scalars(select(Appointment)).all() == [old]  # the new row was rolled back
    assert set(_reminders(db, old.id).values()) == {"scheduled"}
    # The new office booking was given back, so the office only holds the old one.
    assert list(mock_provider._bookings) == [old.external_ref]


def test_cannot_reschedule_someone_elses_appointment(
    client, db, make_user, margaret, chen, mock_provider
):
    old = _book(db, margaret, chen, mock_provider)
    slot = _slots(db, margaret, chen, mock_provider)[1]
    client.login_as(make_user("David"))

    response = _propose(
        client, "reschedule_appointment", appointment_id=str(old.id), slot_id=slot.slot_id
    )

    assert response.json()["detail"]["code"] == "appointment_not_found"


def test_double_confirm_reschedules_once(client, db, margaret, chen, mock_provider):
    old = _book(db, margaret, chen, mock_provider)
    slot = _slots(db, margaret, chen, mock_provider)[1]
    client.login_as(margaret)
    proposed = _propose(
        client, "reschedule_appointment", appointment_id=str(old.id), slot_id=slot.slot_id
    )

    first = _confirm(client, proposed)
    second = _confirm(client, proposed)

    assert first.json() == second.json()
    assert len(db.scalars(select(Appointment)).all()) == 2  # old (cancelled) + one new
