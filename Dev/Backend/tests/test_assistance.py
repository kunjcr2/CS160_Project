"""PB-06 human assistance (S4-12), simple version: asking for help is confirmed first,
lands in a support queue, and only support agents can see and update that queue."""

import pytest
from sqlalchemy import select

from app.model.entities import AssistanceRequest, ConsentGrant, User
from app.views import messages


@pytest.fixture
def margaret(make_user):
    return make_user("Margaret")


@pytest.fixture
def agent(db) -> User:
    riley = User(
        role="support_agent", email="riley@example.com", password_hash="x", display_name="Riley"
    )
    db.add(riley)
    db.commit()
    return riley


def _ask(client, older_adult_id, summary="I can't find my appointment.", **extra):
    return client.post(
        "/api/v1/actions",
        json={
            "action_type": "request_help",
            "payload": {"older_adult_id": str(older_adult_id), "summary": summary, **extra},
        },
    )


def _ask_and_confirm(client, older_adult_id, **kwargs):
    proposed = _ask(client, older_adult_id, **kwargs)
    return client.post(f"/api/v1/actions/{proposed.json()['id']}/confirm")


def _rows(db) -> list[AssistanceRequest]:
    return list(db.scalars(select(AssistanceRequest)))


# --- Asking for help --------------------------------------------------------------------


def test_help_request_is_saved_only_after_a_yes(client, db, margaret):
    client.login_as(margaret)

    proposed = _ask(client, margaret.id, "I need help with my pills.")

    assert proposed.status_code == 201
    assert proposed.json()["summary_text"] == messages.HELP_CONFIRM.format(
        summary="I need help with my pills."
    )
    assert _rows(db) == []

    confirmed = client.post(f"/api/v1/actions/{proposed.json()['id']}/confirm")

    assert confirmed.status_code == 200
    assert confirmed.json()["action"]["status"] == "executed"
    assert confirmed.json()["message"] == messages.HELP_REQUESTED  # says what happens next
    [row] = _rows(db)
    assert (row.user_id, row.requested_by) == (margaret.id, margaret.id)
    assert (row.status, row.reason) == ("open", "user_request")
    assert row.summary == "I need help with my pills."


def test_no_summary_is_fine(client, db, margaret):
    client.login_as(margaret)

    proposed = _ask(client, margaret.id, summary="")
    client.post(f"/api/v1/actions/{proposed.json()['id']}/confirm")

    assert proposed.json()["summary_text"] == messages.HELP_CONFIRM_NO_SUMMARY
    assert _rows(db)[0].summary is None


def test_saying_no_queues_nothing(client, db, margaret):
    client.login_as(margaret)
    proposed = _ask(client, margaret.id)

    client.post(f"/api/v1/actions/{proposed.json()['id']}/cancel")

    assert _rows(db) == []


def test_repeated_failures_reason_is_recorded(client, db, margaret):
    client.login_as(margaret)

    _ask_and_confirm(client, margaret.id, reason="repeated_failures")

    assert _rows(db)[0].reason == "repeated_failures"


def test_unknown_reason_is_refused(client, margaret):
    client.login_as(margaret)

    response = _ask(client, margaret.id, reason="bored")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "invalid_reason"


def test_asking_twice_keeps_one_request(client, db, margaret):
    client.login_as(margaret)
    _ask_and_confirm(client, margaret.id)

    again = _ask(client, margaret.id, "Hello?")

    assert again.status_code == 409
    assert again.json()["detail"] == {
        "code": "already_requested",
        "message": messages.HELP_ALREADY_REQUESTED,
    }
    assert len(_rows(db)) == 1


def test_emergency_wording_gets_911_instead_of_the_queue(client, db, margaret):
    client.login_as(margaret)

    response = _ask(client, margaret.id, "I have chest pain")

    assert response.status_code == 409
    assert response.json()["detail"]["message"] == messages.EMERGENCY_DETECTED
    assert _rows(db) == []


def test_long_summary_is_refused(client, margaret):
    client.login_as(margaret)

    response = _ask(client, margaret.id, "x" * 301)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "summary_too_long"


def test_caregiver_needs_profile_manage_consent(client, db, margaret):
    carer = User(role="caregiver", email="d@example.com", password_hash="x", display_name="Dan")
    db.add(carer)
    db.flush()
    grant = ConsentGrant(
        older_adult_id=margaret.id, caregiver_id=carer.id, scopes=["appointments:read"]
    )
    db.add(grant)
    db.commit()
    client.login_as(carer)

    refused = _ask(client, margaret.id)
    grant.scopes = ["profile:manage"]
    db.commit()
    allowed = _ask_and_confirm(client, margaret.id)

    assert refused.json()["detail"]["code"] == "not_allowed"
    assert allowed.json()["action"]["status"] == "executed"
    assert _rows(db)[0].requested_by == carer.id


def test_cannot_ask_for_someone_else(client, make_user, margaret):
    client.login_as(make_user("David"))

    response = _ask(client, margaret.id)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "not_allowed"


# --- The support queue ------------------------------------------------------------------


def test_agent_sees_the_queue_oldest_first(client, db, make_user, margaret, agent):
    david = make_user("David")
    for person in (margaret, david):
        client.login_as(person)
        _ask_and_confirm(client, person.id, summary=f"{person.display_name} needs help")

    client.login_as(agent)
    queue = client.get("/api/v1/assistance/queue")

    assert queue.status_code == 200
    assert [r["older_adult_name"] for r in queue.json()] == ["Margaret", "David"]
    assert queue.json()[0]["summary"] == "Margaret needs help"
    assert queue.json()[0]["status"] == "open"


def test_only_agents_see_the_queue(client, margaret):
    client.login_as(margaret)

    assert client.get("/api/v1/assistance/queue").status_code == 403


def test_agent_takes_then_resolves_a_request(client, db, margaret, agent):
    client.login_as(margaret)
    _ask_and_confirm(client, margaret.id)
    request_id = _rows(db)[0].id

    client.login_as(agent)
    taken = client.patch(f"/api/v1/assistance/{request_id}", json={"status": "in_progress"})
    resolved = client.patch(f"/api/v1/assistance/{request_id}", json={"status": "resolved"})

    assert taken.status_code == 200
    assert taken.json()["status"] == "in_progress"
    assert taken.json()["assigned_to_name"] == "Riley"
    assert resolved.status_code == 200
    assert resolved.json()["resolved_at"] is not None
    assert client.get("/api/v1/assistance/queue").json() == []  # resolved leaves the queue

    again = client.patch(f"/api/v1/assistance/{request_id}", json={"status": "resolved"})
    assert again.status_code == 409


def test_after_resolving_the_user_can_ask_again(client, db, margaret, agent):
    client.login_as(margaret)
    _ask_and_confirm(client, margaret.id)
    client.login_as(agent)
    client.patch(f"/api/v1/assistance/{_rows(db)[0].id}", json={"status": "resolved"})

    client.login_as(margaret)
    second = _ask_and_confirm(client, margaret.id, summary="Something else")

    assert second.json()["action"]["status"] == "executed"
    assert len(_rows(db)) == 2


def test_two_agents_cannot_both_take_it(client, db, margaret, agent):
    other = User(
        role="support_agent", email="sam@example.com", password_hash="x", display_name="Sam"
    )
    db.add(other)
    db.commit()
    client.login_as(margaret)
    _ask_and_confirm(client, margaret.id)
    request_id = _rows(db)[0].id

    client.login_as(agent)
    first = client.patch(f"/api/v1/assistance/{request_id}", json={"status": "in_progress"})
    repeat = client.patch(f"/api/v1/assistance/{request_id}", json={"status": "in_progress"})
    client.login_as(other)
    second = client.patch(f"/api/v1/assistance/{request_id}", json={"status": "in_progress"})

    assert first.status_code == repeat.status_code == 200  # taking it twice is harmless
    assert second.status_code == 409


def test_older_adult_cannot_update_requests(client, db, margaret):
    client.login_as(margaret)
    _ask_and_confirm(client, margaret.id)

    response = client.patch(f"/api/v1/assistance/{_rows(db)[0].id}", json={"status": "resolved"})

    assert response.status_code == 403
