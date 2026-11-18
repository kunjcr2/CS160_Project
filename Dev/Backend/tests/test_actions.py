"""Confirmation pipeline (S2-08, plan §5.3): nothing executes without a yes; confirming
twice executes once."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.model.commands import ActionCommand, ActionNotPossible, register
from app.model.entities import PendingAction, Provider
from app.model.services.action_service import ActionNotFound, ActionNotPending, ActionService
from app.views import messages

executed: list[dict] = []


@register
class SaveNote(ActionCommand):
    """Test-only command. Writes a Provider row so rollback of partial writes is visible."""

    action_type = "test_save_note"

    def summary(self, session):
        return f"Save the note '{self.payload['text']}'. Should I do it?"

    def revalidate(self, session):
        if self.payload.get("blocked"):
            raise ActionNotPossible("blocked", "I can't do that right now.")

    def execute(self, session):
        session.add(
            Provider(name="Note", specialty="-", location="-", external_ref=self.payload["text"])
        )
        session.flush()
        if self.payload.get("crash_after_write"):
            raise RuntimeError("provider is down")
        executed.append(self.payload)
        return {"note": self.payload["text"]}

    def success_message(self, result):
        return "Saved."


@pytest.fixture(autouse=True)
def _reset_executed():
    executed.clear()


def _providers(db) -> int:
    return db.scalar(select(func.count()).select_from(Provider))


# --- API --------------------------------------------------------------------------------


def _propose(client, text="hello", **extra):
    response = client.post(
        "/api/v1/actions",
        json={"action_type": "test_save_note", "payload": {"text": text, **extra}},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_requests_without_a_user_are_rejected(client):
    assert client.get("/api/v1/actions/pending").status_code == 401


def test_propose_does_not_execute(client, make_user):
    client.login_as(make_user())
    action = _propose(client)

    assert action["status"] == "proposed"
    assert action["summary_text"] == "Save the note 'hello'. Should I do it?"
    assert executed == []
    assert client.get("/api/v1/actions/pending").json()["action"]["id"] == action["id"]


def test_confirm_executes_and_double_confirm_executes_once(client, make_user, db):
    client.login_as(make_user())
    action = _propose(client)

    first = client.post(f"/api/v1/actions/{action['id']}/confirm")
    second = client.post(f"/api/v1/actions/{action['id']}/confirm")

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["action"]["status"] == "executed"
    assert first.json()["action"]["result"] == {"note": "hello"}
    assert first.json()["message"] == "Saved."
    assert len(executed) == 1
    assert _providers(db) == 1
    assert client.get("/api/v1/actions/pending").json()["action"] is None


def test_another_user_cannot_confirm_or_cancel(client, make_user):
    client.login_as(make_user("Margaret"))
    action = _propose(client)

    client.login_as(make_user("David"))
    assert client.post(f"/api/v1/actions/{action['id']}/confirm").status_code == 404
    assert client.post(f"/api/v1/actions/{action['id']}/cancel").status_code == 404
    assert executed == []


def test_cancel_then_confirm_does_nothing(client, make_user):
    client.login_as(make_user())
    action = _propose(client)

    cancelled = client.post(f"/api/v1/actions/{action['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["message"] == messages.ACTION_CANCELLED
    assert client.post(f"/api/v1/actions/{action['id']}/cancel").status_code == 200  # twice is ok

    confirmed = client.post(f"/api/v1/actions/{action['id']}/confirm")
    assert confirmed.status_code == 409
    assert confirmed.json()["detail"]["code"] == "cancelled"
    assert executed == []


def test_confirm_after_expiry_is_rejected(client, make_user, db):
    client.login_as(make_user())
    action = _propose(client)
    row = db.get(PendingAction, action["id"])
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()

    response = client.post(f"/api/v1/actions/{action['id']}/confirm")

    assert response.status_code == 409
    assert response.json()["detail"] == {"code": "expired", "message": messages.ACTION_EXPIRED}
    db.refresh(row)
    assert row.status == "expired"
    assert executed == []


def test_new_proposal_replaces_the_old_one(client, make_user, db):
    client.login_as(make_user())
    old = _propose(client, "first")
    new = _propose(client, "second")

    assert db.get(PendingAction, old["id"]).status == "cancelled"
    assert client.get("/api/v1/actions/pending").json()["action"]["id"] == new["id"]
    assert client.post(f"/api/v1/actions/{old['id']}/confirm").status_code == 409


def test_unknown_action_type_is_rejected(client, make_user):
    client.login_as(make_user())
    response = client.post("/api/v1/actions", json={"action_type": "launch_rocket", "payload": {}})
    assert response.status_code == 422


def test_propose_is_rejected_when_the_action_is_not_possible(client, make_user):
    client.login_as(make_user())
    response = client.post(
        "/api/v1/actions",
        json={"action_type": "test_save_note", "payload": {"text": "x", "blocked": True}},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "blocked"


# --- Service ----------------------------------------------------------------------------


def test_failure_at_confirm_is_recorded_and_partial_writes_are_undone(db, make_user):
    user = make_user()
    service = ActionService(db)
    action = service.propose(user, "test_save_note", {"text": "x", "crash_after_write": True})
    db.commit()

    outcome = service.confirm(action.id, user)
    db.commit()

    assert outcome.action.status == "failed"
    assert outcome.message == messages.SERVICE_UNAVAILABLE
    assert _providers(db) == 0  # the Provider row written before the crash was rolled back
    assert service.confirm(action.id, user).message == messages.SERVICE_UNAVAILABLE  # retry


def test_revalidation_failure_at_confirm_explains_why(db, make_user):
    user = make_user()
    service = ActionService(db)
    action = service.propose(user, "test_save_note", {"text": "x"})
    action.payload = {"text": "x", "blocked": True}  # the world changed after proposing
    db.commit()

    outcome = service.confirm(action.id, user)

    assert outcome.action.status == "failed"
    assert outcome.message == "I can't do that right now."
    assert executed == []


def test_service_raises_for_missing_and_not_pending_actions(db, make_user):
    user = make_user()
    service = ActionService(db)
    action = service.propose(user, "test_save_note", {"text": "x"})
    service.confirm(action.id, user)

    with pytest.raises(ActionNotFound):
        service.confirm(uuid.uuid4(), user)
    with pytest.raises(ActionNotPending):
        service.cancel(action.id, user)  # already executed


def test_expiry_uses_the_injected_clock(db, make_user):
    user = make_user()
    now = datetime(2026, 10, 20, 17, 0, tzinfo=UTC)
    service = ActionService(db, clock=lambda: now, ttl=timedelta(minutes=5))
    action = service.propose(user, "test_save_note", {"text": "x"})

    assert action.expires_at == now + timedelta(minutes=5)
    later = ActionService(db, clock=lambda: now + timedelta(minutes=6))
    assert later.get_pending(user) is None
    assert action.status == "expired"
