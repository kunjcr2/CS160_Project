"""PB-01 booking (S2-09): Margaret's cardiology appointment is booked after a yes; a slot
taken in the meantime is handled."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from conftest import next_tuesday
from sqlalchemy import func, select

from app.adapters.healthcare.interface import ProviderUnavailableError
from app.model.entities import Appointment, Provider
from app.model.services.action_service import ActionService
from app.model.services.appointment_service import AppointmentService
from app.views import messages
from app.views.formatting import spoken_date_time, spoken_list, spoken_time

LA = ZoneInfo("America/Los_Angeles")


@pytest.fixture(autouse=True)
def _fresh_provider(mock_provider):
    """Every booking test gets its own mock provider (see conftest)."""


def _appointments(db) -> int:
    return db.scalar(select(func.count()).select_from(Appointment))


# --- Full flow through the API ----------------------------------------------------------


def test_margaret_books_her_cardiology_appointment_after_a_yes(client, make_user, chen, db):
    client.login_as(make_user("Margaret"))
    tuesday = next_tuesday()

    providers = client.get("/api/v1/providers", params={"name": "Dr. Chen"}).json()
    assert [p["name"] for p in providers] == ["Dr. Lisa Chen"]

    slots = client.get(
        "/api/v1/slots",
        params={"provider_id": providers[0]["id"], "from": tuesday, "to": tuesday},
    ).json()
    assert 1 <= len(slots) <= 3
    slot = slots[0]
    starts_at = datetime.fromisoformat(slot["starts_at"])
    assert starts_at.astimezone(LA).date() == tuesday
    assert slot["label"] == spoken_date_time(starts_at, "America/Los_Angeles")

    proposed = client.post(
        "/api/v1/actions",
        json={"action_type": "book_appointment", "payload": {"slot_id": slot["slot_id"]}},
    ).json()
    assert proposed["summary_text"] == (
        f"Dr. Lisa Chen, Cardiology, {spoken_date_time(starts_at, 'America/Los_Angeles')}, "
        "at Valley Medical, Building B. Should I book it?"
    )
    assert _appointments(db) == 0  # nothing is booked before the yes

    confirmed = client.post(f"/api/v1/actions/{proposed['id']}/confirm").json()

    assert confirmed["action"]["status"] == "executed"
    assert confirmed["message"].startswith("Done. You're booked with Dr. Lisa Chen on")
    assert spoken_time(starts_at, "America/Los_Angeles") in confirmed["message"]
    upcoming = client.get("/api/v1/appointments").json()
    assert [a["id"] for a in upcoming] == [confirmed["action"]["result"]["appointment_id"]]
    assert upcoming[0]["status"] == "booked"
    assert upcoming[0]["provider"]["name"] == "Dr. Lisa Chen"
    appointment = db.get(Appointment, upcoming[0]["id"])
    assert appointment.external_ref.startswith("mock-appt-")


def test_slot_taken_between_proposal_and_yes_is_explained(
    client, make_user, chen, db, mock_provider
):
    margaret, david = make_user("Margaret"), make_user("David")
    service = AppointmentService(db, healthcare=mock_provider)
    slot = service.find_slots(margaret, chen, next_tuesday(), next_tuesday())[0]

    client.login_as(margaret)
    proposed = client.post(
        "/api/v1/actions",
        json={"action_type": "book_appointment", "payload": {"slot_id": slot.slot_id}},
    ).json()

    # David books the same slot before Margaret says yes.
    actions = ActionService(db, healthcare=mock_provider)
    davids = actions.propose(david, "book_appointment", {"slot_id": slot.slot_id})
    assert actions.confirm(davids.id, david).action.status == "executed"
    db.commit()

    response = client.post(f"/api/v1/actions/{proposed['id']}/confirm")

    assert response.status_code == 200
    assert response.json()["action"]["status"] == "failed"
    assert response.json()["message"].startswith(
        "Sorry, that time was just taken. The next open times are: "
    )
    assert spoken_date_time(slot.starts_at, "America/Los_Angeles") not in response.json()["message"]
    assert _appointments(db) == 1  # only David's


def test_an_already_booked_slot_cannot_be_proposed(client, make_user, chen, db, mock_provider):
    margaret, david = make_user("Margaret"), make_user("David")
    slot = AppointmentService(db, healthcare=mock_provider).find_slots(
        margaret, chen, next_tuesday(), next_tuesday()
    )[0]
    actions = ActionService(db, healthcare=mock_provider)
    actions.confirm(actions.propose(david, "book_appointment", {"slot_id": slot.slot_id}).id, david)
    db.commit()

    client.login_as(margaret)
    response = client.post(
        "/api/v1/actions",
        json={"action_type": "book_appointment", "payload": {"slot_id": slot.slot_id}},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "slot_taken"


def test_booked_slots_are_not_offered_again(make_user, chen, db, mock_provider):
    margaret = make_user()
    service = AppointmentService(db, healthcare=mock_provider)
    first = service.find_slots(margaret, chen, next_tuesday(), next_tuesday())
    actions = ActionService(db, healthcare=mock_provider)
    actions.confirm(
        actions.propose(margaret, "book_appointment", {"slot_id": first[0].slot_id}).id, margaret
    )

    again = service.find_slots(margaret, chen, next_tuesday(), next_tuesday())
    assert first[0].slot_id not in [option.slot_id for option in again]


def test_provider_down_at_confirm_offers_the_office_phone(
    client, make_user, chen, db, mock_provider, monkeypatch
):
    client.login_as(make_user())
    slot = client.get(
        "/api/v1/slots", params={"provider_id": chen.id, "from": next_tuesday()}
    ).json()[0]
    proposed = client.post(
        "/api/v1/actions",
        json={"action_type": "book_appointment", "payload": {"slot_id": slot["slot_id"]}},
    ).json()

    def provider_down(*args, **kwargs):
        raise ProviderUnavailableError("down")

    # Every call to the provider fails from now on.
    monkeypatch.setattr(mock_provider, "find_slots", provider_down)
    monkeypatch.setattr(mock_provider, "book", provider_down)
    response = client.post(f"/api/v1/actions/{proposed['id']}/confirm").json()

    assert response["action"]["status"] == "failed"
    assert response["message"] == messages.BOOKING_FAILED.format(phone="408-555-0142")
    assert _appointments(db) == 0
    slots = client.get("/api/v1/slots", params={"provider_id": chen.id})
    assert slots.status_code == 503


def test_provider_failing_during_booking_leaves_nothing_behind(
    make_user, chen, db, mock_provider, monkeypatch
):
    margaret = make_user()
    slot = AppointmentService(db, healthcare=mock_provider).find_slots(
        margaret, chen, next_tuesday(), next_tuesday()
    )[0]
    actions = ActionService(db, healthcare=mock_provider)
    action = actions.propose(margaret, "book_appointment", {"slot_id": slot.slot_id})

    def provider_down(*args, **kwargs):
        raise ProviderUnavailableError("down")

    monkeypatch.setattr(mock_provider, "book", provider_down)
    outcome = actions.confirm(action.id, margaret)

    assert outcome.action.status == "failed"
    assert outcome.message == messages.BOOKING_FAILED.format(phone="408-555-0142")
    assert _appointments(db) == 0  # the row claimed before calling the provider is undone


def test_unknown_slot_cannot_be_proposed(client, make_user, chen):
    client.login_as(make_user())
    for slot_id in ["nonsense", "prac-nobody|20301020T1730Z"]:
        response = client.post(
            "/api/v1/actions",
            json={"action_type": "book_appointment", "payload": {"slot_id": slot_id}},
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "slot_not_found"


def test_users_cannot_see_each_others_appointments(client, make_user, chen, db, mock_provider):
    margaret, david = make_user("Margaret"), make_user("David")
    slot = AppointmentService(db, healthcare=mock_provider).find_slots(
        margaret, chen, next_tuesday(), next_tuesday()
    )[0]
    actions = ActionService(db, healthcare=mock_provider)
    result = actions.confirm(
        actions.propose(margaret, "book_appointment", {"slot_id": slot.slot_id}).id, margaret
    )
    db.commit()
    appointment_id = result.action.result["data"]["appointment_id"]

    client.login_as(david)
    assert client.get("/api/v1/appointments").json() == []
    assert client.get(f"/api/v1/appointments/{appointment_id}").status_code == 404

    client.login_as(margaret)
    assert client.get(f"/api/v1/appointments/{appointment_id}").status_code == 200


# --- Provider lookup, mock provider, formatting -----------------------------------------


def test_provider_name_matching(db, mock_provider):
    db.add_all(
        [
            Provider(name="Dr. Lisa Chen", specialty="Cardiology", location="A", external_ref="a"),
            Provider(
                name="Dr. Amy Lee", specialty="Physical therapy", location="B", external_ref="b"
            ),
            Provider(
                name="Dr. Brian Lee", specialty="Primary care", location="C", external_ref="c"
            ),
        ]
    )
    db.commit()
    service = AppointmentService(db, healthcare=mock_provider)

    assert [p.name for p in service.find_providers("Dr. Chen")] == ["Dr. Lisa Chen"]
    assert [p.name for p in service.find_providers("chen")] == ["Dr. Lisa Chen"]
    assert len(service.find_providers("Dr. Lee")) == 2  # ambiguous: ask which one
    assert service.find_providers("Dr. Smith") == []
    assert service.find_providers("Dr.") == []
    assert len(service.find_providers()) == 3


def test_spoken_formats():
    moment = datetime(2026, 10, 20, 16, 0, tzinfo=UTC)  # 9:00 AM in Los Angeles
    assert spoken_date_time(moment, "America/Los_Angeles") == "Tuesday, October 20 at 9:00 AM"
    assert spoken_time(moment, "America/New_York") == "12:00 PM"
    assert spoken_list(["a"]) == "a"
    assert spoken_list(["a", "b"]) == "a or b"
    assert spoken_list(["a", "b", "c"]) == "a, b, or c"
