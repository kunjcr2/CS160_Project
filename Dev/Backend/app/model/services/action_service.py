"""ActionService: propose, confirm, and cancel pending actions (plan §4, §5.3).

confirm() is a Template Method: ownership → status → expiry → revalidate → execute →
record → publish. No feature can skip or reorder these steps; a feature only adds a
Command class. The caller (controller) commits the session afterwards.
"""

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.model import commands
from app.model.commands import ActionNotPossible
from app.model.entities import PendingAction, User
from app.model.events import ActionExecuted, events
from app.model.repositories import pending_actions as repo
from app.views import messages

log = logging.getLogger(__name__)

DEFAULT_TTL = timedelta(minutes=5)


class ActionNotFound(Exception):  # noqa: N818
    """No such action, or it belongs to someone else (both look the same: 404)."""


class ActionNotPending(Exception):  # noqa: N818
    """The action was cancelled, expired, or replaced, so it can't be confirmed (409)."""

    def __init__(self, action: PendingAction, message: str) -> None:
        super().__init__(message)
        self.action = action
        self.message = message


@dataclass(frozen=True)
class ActionOutcome:
    action: PendingAction
    message: str  # the sentence to show or speak


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ActionService:
    def __init__(
        self,
        session: Session,
        *,
        clock: Callable[[], datetime] = _utcnow,
        ttl: timedelta = DEFAULT_TTL,
    ) -> None:
        self.session = session
        self.clock = clock
        self.ttl = ttl

    def propose(self, user: User, action_type: str, payload: dict) -> PendingAction:
        """Validate the action and store it as `proposed`. Never executes anything.

        Raises UnknownActionType or ActionNotPossible (e.g. the slot is already taken).
        """
        command = commands.build(action_type, user, payload)
        command.revalidate(self.session)
        summary = command.summary(self.session)

        repo.lock_user(self.session, user.id)
        repo.cancel_proposed(self.session, user.id)  # one proposed action per user
        action = PendingAction(
            user_id=user.id,
            action_type=action_type,
            payload=payload,
            summary_text=summary,
            status="proposed",
            idempotency_key=uuid.uuid4().hex,
            expires_at=self.clock() + self.ttl,
        )
        self.session.add(action)
        self.session.flush()
        return action

    def get_pending(self, user: User) -> PendingAction | None:
        """The user's proposed action, if it hasn't expired."""
        action = repo.get_proposed(self.session, user.id)
        if action is not None and self._expire_if_due(action):
            return None
        return action

    def confirm(self, action_id: uuid.UUID, user: User) -> ActionOutcome:
        """Execute a proposed action. Safe to call twice: the second call returns the first
        call's result without executing again.

        Returns an outcome whose action.status is `executed`, `failed`, or `expired`.
        Raises ActionNotFound or ActionNotPending.
        """
        action = repo.lock_owned(self.session, action_id, user.id)
        if action is None:
            raise ActionNotFound(action_id)
        if action.status in ("executed", "failed"):  # double tap or retry: same answer
            return ActionOutcome(action, action.result["message"])
        if action.status != "proposed":
            raise ActionNotPending(action, _not_pending_message(action.status))
        if self._expire_if_due(action):
            return ActionOutcome(action, messages.ACTION_EXPIRED)

        command = commands.build(action.action_type, user, action.payload)
        action.status = "confirmed"
        try:
            # Savepoint: if anything below fails, its database writes are undone, but the
            # action row can still be marked `failed` in the outer transaction.
            with self.session.begin_nested():
                command.revalidate(self.session)
                data = command.execute(self.session)
                events.publish(
                    self.session, ActionExecuted(action.id, user.id, action.action_type, data)
                )
        except ActionNotPossible as error:
            action.status = "failed"
            action.result = {"error": error.code, "message": error.message}
        except Exception:
            log.exception("Action %s (%s) failed", action.id, action.action_type)
            action.status = "failed"
            action.result = {
                "error": "service_unavailable",
                "message": messages.SERVICE_UNAVAILABLE,
            }
        else:
            action.status = "executed"
            action.result = {"data": data, "message": command.success_message(data)}
        self.session.flush()
        return ActionOutcome(action, action.result["message"])

    def cancel(self, action_id: uuid.UUID, user: User) -> ActionOutcome:
        """The user said no. Cancelling twice is fine. Raises ActionNotFound or
        ActionNotPending (already executed, failed, or expired)."""
        action = repo.lock_owned(self.session, action_id, user.id)
        if action is None:
            raise ActionNotFound(action_id)
        if action.status == "proposed" and not self._expire_if_due(action):
            action.status = "cancelled"
            self.session.flush()
        if action.status != "cancelled":
            raise ActionNotPending(action, _not_pending_message(action.status))
        return ActionOutcome(action, messages.ACTION_CANCELLED)

    def _expire_if_due(self, action: PendingAction) -> bool:
        if action.expires_at > self.clock():
            return False
        action.status = "expired"
        self.session.flush()
        return True


def _not_pending_message(status: str) -> str:
    if status == "expired":
        return messages.ACTION_EXPIRED
    if status == "executed":
        return messages.ACTION_ALREADY_DONE
    return messages.ACTION_NOT_PENDING
