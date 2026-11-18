"""PB-04 prescription refills (S4-11): nothing reaches the pharmacy without a yes, the
right medicine is found from what the user said, and the status can be read back."""

from datetime import UTC, datetime, time, timedelta

import pytest
from sqlalchemy import select

from app.adapters.pharmacy.mock import MockPharmacy
from app.controllers.dependencies import get_pharmacy
from app.main import app
from app.model.entities import ConsentGrant, Medication, RefillRequest, User
from app.model.entities.medication import EVERY_DAY
from app.model.services.medication_service import create_medication
from app.model.services.refill_service import match_medications
from app.views import messages


@pytest.fixture(autouse=True)
def _fresh_pharmacy(mock_pharmacy):
    """Every refill test gets its own mock pharmacy (see conftest)."""


def _add(db, owner, name, dosage, instructions=None, refills=2) -> Medication:
    medication = create_medication(
        db,
        owner.id,
        name=name,
        dosage=dosage,
        instructions=instructions,
        refills_remaining=refills,
        schedules=[(time(8, 0), list(EVERY_DAY))],
        now=datetime.now(UTC),
    )
    db.commit()
    return medication


@pytest.fixture
def margaret(make_user):
    return make_user("Margaret")


@pytest.fixture
def lisinopril(db, margaret):
    return _add(db, margaret, "Lisinopril", "10 mg", "For blood pressure", refills=2)


@pytest.fixture
def metformin(db, margaret):
    return _add(db, margaret, "Metformin", "500 mg", "Take with food", refills=3)


def _propose(client, older_adult_id, **what):
    return client.post(
        "/api/v1/actions",
        json={
            "action_type": "request_refill",
            "payload": {"older_adult_id": str(older_adult_id), **what},
        },
    )


def _requests(db) -> list[RefillRequest]:
    return list(db.scalars(select(RefillRequest)))


# --- The happy path ---------------------------------------------------------------------


def test_refill_is_sent_only_after_a_yes(client, db, margaret, lisinopril, mock_pharmacy):
    client.login_as(margaret)

    proposed = _propose(client, margaret.id, medication_name="my blood pressure pill")

    assert proposed.status_code == 201
    assert proposed.json()["summary_text"] == messages.REFILL_CONFIRM.format(
        name="Lisinopril", dosage="10 mg"
    )
    assert _requests(db) == []  # nothing sent before the yes

    confirmed = client.post(f"/api/v1/actions/{proposed.json()['id']}/confirm")

    assert confirmed.status_code == 200
    assert confirmed.json()["action"]["status"] == "executed"
    assert confirmed.json()["message"] == messages.REFILL_REQUESTED.format(name="Lisinopril")
    [request] = _requests(db)
    assert request.status == "requested"
    assert request.user_id == margaret.id
    assert request.requested_by == margaret.id
    assert request.external_ref.startswith("mock-rx-")
    db.refresh(lisinopril)
    assert lisinopril.refills_remaining == 1


def test_cancel_sends_nothing(client, db, margaret, lisinopril):
    client.login_as(margaret)
    proposed = _propose(client, margaret.id, medication_id=str(lisinopril.id))

    client.post(f"/api/v1/actions/{proposed.json()['id']}/cancel")

    assert _requests(db) == []
    db.refresh(lisinopril)
    assert lisinopril.refills_remaining == 2


def test_double_confirm_sends_one_refill(client, db, margaret, lisinopril):
    client.login_as(margaret)
    proposed = _propose(client, margaret.id, medication_id=str(lisinopril.id))

    first = client.post(f"/api/v1/actions/{proposed.json()['id']}/confirm")
    second = client.post(f"/api/v1/actions/{proposed.json()['id']}/confirm")

    assert first.json() == second.json()
    assert len(_requests(db)) == 1
    db.refresh(lisinopril)
    assert lisinopril.refills_remaining == 1


# --- Finding the medicine ---------------------------------------------------------------


def test_matching_prefers_the_name_then_the_instructions(db, margaret, lisinopril, metformin):
    assert match_medications(db, margaret.id, "Metformin refill please") == [metformin]
    assert match_medications(db, margaret.id, "blood pressure pills") == [lisinopril]
    assert match_medications(db, margaret.id, "my pills") == []  # only filler words


def test_unclear_medicine_asks_which_one(client, db, margaret):
    _add(db, margaret, "Carvedilol", "6.25 mg", "Take with food")
    _add(db, margaret, "Metformin", "500 mg", "Take with food")
    client.login_as(margaret)

    response = _propose(client, margaret.id, medication_name="the one I take with food")

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "medication_unclear",
        "message": messages.REFILL_WHICH_ONE.format(options="Carvedilol or Metformin"),
    }


def test_unknown_medicine_is_refused(client, margaret, lisinopril):
    client.login_as(margaret)

    response = _propose(client, margaret.id, medication_name="aspirin")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "medication_not_found"


def test_stopped_medicine_is_unknown(client, db, margaret, lisinopril):
    lisinopril.stopped_at = datetime.now(UTC)
    db.commit()
    client.login_as(margaret)

    response = _propose(client, margaret.id, medication_id=str(lisinopril.id))

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "medication_not_found"


# --- Edge cases (plan §8 PB-04) ---------------------------------------------------------


def test_no_refills_left_points_to_the_doctor(client, db, margaret):
    atorvastatin = _add(db, margaret, "Atorvastatin", "20 mg", refills=0)
    client.login_as(margaret)

    response = _propose(client, margaret.id, medication_id=str(atorvastatin.id))

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "no_refills",
        "message": messages.REFILL_NONE_LEFT.format(name="Atorvastatin"),
    }


def test_second_request_while_one_is_open_is_refused(client, db, margaret, lisinopril):
    client.login_as(margaret)
    first = _propose(client, margaret.id, medication_id=str(lisinopril.id))
    client.post(f"/api/v1/actions/{first.json()['id']}/confirm")

    again = _propose(client, margaret.id, medication_id=str(lisinopril.id))

    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "already_requested"
    assert len(_requests(db)) == 1


def test_pharmacy_down_changes_nothing(client, db, margaret, lisinopril):
    client.login_as(margaret)
    proposed = _propose(client, margaret.id, medication_id=str(lisinopril.id))
    app.dependency_overrides[get_pharmacy] = lambda: MockPharmacy(failure_rate=1.0)

    confirmed = client.post(f"/api/v1/actions/{proposed.json()['id']}/confirm")

    assert confirmed.status_code == 200
    assert confirmed.json()["action"]["status"] == "failed"
    assert confirmed.json()["message"] == messages.REFILL_FAILED
    assert _requests(db) == []
    db.refresh(lisinopril)
    assert lisinopril.refills_remaining == 2  # the savepoint rolled the decrement back


# --- Who may ask ------------------------------------------------------------------------


def _caregiver(db, margaret, scopes) -> User:
    carer = User(
        role="caregiver", email="daniel@example.com", password_hash="x", display_name="Daniel"
    )
    db.add(carer)
    db.flush()
    db.add(ConsentGrant(older_adult_id=margaret.id, caregiver_id=carer.id, scopes=scopes))
    db.commit()
    return carer


def test_caregiver_with_manage_consent_can_request(client, db, margaret, lisinopril):
    carer = _caregiver(db, margaret, ["medications:read", "medications:manage"])
    client.login_as(carer)

    proposed = _propose(client, margaret.id, medication_id=str(lisinopril.id))
    client.post(f"/api/v1/actions/{proposed.json()['id']}/confirm")

    [request] = _requests(db)
    assert request.user_id == margaret.id
    assert request.requested_by == carer.id


def test_caregiver_with_read_only_consent_cannot_request(client, db, margaret, lisinopril):
    client.login_as(_caregiver(db, margaret, ["medications:read"]))

    response = _propose(client, margaret.id, medication_id=str(lisinopril.id))

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "not_allowed"


def test_someone_else_cannot_refill_or_see_refills(client, make_user, margaret, lisinopril):
    client.login_as(make_user("David"))

    proposed = _propose(client, margaret.id, medication_id=str(lisinopril.id))
    listed = client.get(f"/api/v1/older-adults/{margaret.id}/refills")

    assert proposed.status_code == 409
    assert proposed.json()["detail"]["code"] == "not_allowed"
    assert listed.status_code == 404


# --- Status -----------------------------------------------------------------------------


def test_status_moves_forward_as_the_pharmacy_works(client, db, margaret, lisinopril):
    now = [datetime.now(UTC)]
    pharmacy = MockPharmacy(
        now=lambda: now[0],
        in_progress_after=timedelta(minutes=1),
        ready_after=timedelta(minutes=30),
    )
    app.dependency_overrides[get_pharmacy] = lambda: pharmacy
    client.login_as(margaret)
    proposed = _propose(client, margaret.id, medication_id=str(lisinopril.id))
    client.post(f"/api/v1/actions/{proposed.json()['id']}/confirm")

    def status():
        [refill] = client.get(f"/api/v1/older-adults/{margaret.id}/refills").json()
        return refill["status"], refill["status_message"]

    assert status() == ("requested", "Your Lisinopril refill request was sent to the pharmacy.")
    now[0] += timedelta(minutes=5)
    assert status() == ("in_progress", "The pharmacy is preparing your Lisinopril.")
    now[0] += timedelta(minutes=30)
    assert status() == ("ready", "Your Lisinopril is ready to pick up.")
    assert db.scalar(select(RefillRequest.status)) == "ready"  # saved, not just shown


def test_status_is_kept_when_the_pharmacy_forgets(client, db, margaret, lisinopril):
    client.login_as(margaret)
    proposed = _propose(client, margaret.id, medication_id=str(lisinopril.id))
    client.post(f"/api/v1/actions/{proposed.json()['id']}/confirm")
    app.dependency_overrides[get_pharmacy] = lambda: MockPharmacy()  # "restarted"

    [refill] = client.get(f"/api/v1/older-adults/{margaret.id}/refills").json()

    assert refill["status"] == "requested"
    assert refill["medication"]["name"] == "Lisinopril"
    assert refill["medication"]["refills_remaining"] == 1
