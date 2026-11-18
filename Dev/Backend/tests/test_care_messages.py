"""PB-07 care-team messaging (send only, plan §17): nothing sends without confirmation,
confirming twice sends once, and the emergency guardrail blocks the send entirely."""

from sqlalchemy import select

from app.adapters.messaging.mock import MockCareMessaging
from app.controllers.dependencies import get_messaging
from app.main import app
from app.model.entities import Message
from app.views import messages


def _propose(client, older_adult_id, provider_id, body="I'm having trouble sleeping."):
    response = client.post(
        "/api/v1/actions",
        json={
            "action_type": "send_care_message",
            "payload": {
                "older_adult_id": str(older_adult_id),
                "provider_id": str(provider_id),
                "body": body,
            },
        },
    )
    return response


def _rows(db) -> list[Message]:
    return list(db.scalars(select(Message)))


def test_confirm_sends_and_saves(client, make_user, chen, db, mock_messaging):
    margaret = make_user()
    client.login_as(margaret)
    proposed = _propose(client, margaret.id, chen.id, "Can we talk about my prescription?")
    assert proposed.status_code == 201
    assert "Dr. Lisa Chen" in proposed.json()["summary_text"]

    confirmed = client.post(f"/api/v1/actions/{proposed.json()['id']}/confirm")

    assert confirmed.status_code == 200
    assert confirmed.json()["action"]["status"] == "executed"
    assert confirmed.json()["message"] == messages.CARE_MESSAGE_SENT.format(doctor=chen.name)
    rows = _rows(db)
    assert len(rows) == 1
    assert rows[0].status == "sent"
    assert rows[0].body == "Can we talk about my prescription?"
    assert rows[0].older_adult_id == margaret.id
    assert rows[0].provider_id == chen.id
    assert rows[0].external_ref is not None


def test_cancel_sends_nothing(client, make_user, chen, db, mock_messaging):
    margaret = make_user()
    client.login_as(margaret)
    proposed = _propose(client, margaret.id, chen.id)

    cancelled = client.post(f"/api/v1/actions/{proposed.json()['id']}/cancel")

    assert cancelled.status_code == 200
    assert _rows(db) == []


def test_double_confirm_sends_once(client, make_user, chen, db, mock_messaging):
    margaret = make_user()
    client.login_as(margaret)
    proposed = _propose(client, margaret.id, chen.id)

    first = client.post(f"/api/v1/actions/{proposed.json()['id']}/confirm")
    second = client.post(f"/api/v1/actions/{proposed.json()['id']}/confirm")

    assert first.json() == second.json()
    assert len(_rows(db)) == 1


def test_emergency_wording_is_refused(client, make_user, chen, db, mock_messaging):
    margaret = make_user()
    client.login_as(margaret)

    response = _propose(client, margaret.id, chen.id, "I think I'm having a heart attack")

    assert response.status_code == 409
    assert response.json()["detail"]["message"] == messages.EMERGENCY_DETECTED
    assert _rows(db) == []


def test_another_user_cannot_see_the_messages(client, make_user, chen, db, mock_messaging):
    margaret = make_user("Margaret")
    client.login_as(margaret)
    proposed = _propose(client, margaret.id, chen.id)
    client.post(f"/api/v1/actions/{proposed.json()['id']}/confirm")

    david = make_user("David")
    client.login_as(david)
    response = client.get(f"/api/v1/older-adults/{margaret.id}/messages")

    assert response.status_code == 404


def test_owner_can_list_their_own_messages(client, make_user, chen, db, mock_messaging):
    margaret = make_user()
    client.login_as(margaret)
    proposed = _propose(client, margaret.id, chen.id, "Hello doctor")
    client.post(f"/api/v1/actions/{proposed.json()['id']}/confirm")

    response = client.get(f"/api/v1/older-adults/{margaret.id}/messages")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["body"] == "Hello doctor"
    assert body[0]["status"] == "sent"
    assert body[0]["provider"]["name"] == "Dr. Lisa Chen"


def test_mock_failing_marks_the_message_failed(client, make_user, chen, db):
    app.dependency_overrides[get_messaging] = lambda: MockCareMessaging(failure_rate=1.0)
    try:
        margaret = make_user()
        client.login_as(margaret)
        proposed = _propose(client, margaret.id, chen.id)

        confirmed = client.post(f"/api/v1/actions/{proposed.json()['id']}/confirm")

        assert confirmed.status_code == 200
        assert confirmed.json()["action"]["status"] == "executed"
        assert confirmed.json()["message"] == messages.CARE_MESSAGE_FAILED.format(doctor=chen.name)
        rows = _rows(db)
        assert len(rows) == 1
        assert rows[0].status == "failed"
        assert rows[0].external_ref is None
    finally:
        app.dependency_overrides.pop(get_messaging, None)
