"""PB-06: ask a support person to contact the older adult (the simple "request help"
version from the plan §17 cut order). The request goes into a queue that support agents
read and update (controllers/assistance.py); nothing else is contacted automatically.

Payload: {"older_adult_id": "...", "summary": "what they were trying to do",
"reason": "user_request" | "repeated_failures"}. summary is optional and short, and is
read back before saving so the user agrees to share it (never the full transcript).
older_adult_id is who needs help (plan §5.2): that older adult, or a caregiver with
"profile:manage" consent for them.
"""

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.model.entities import AssistanceRequest, User
from app.model.entities.assistance_request import (
    ASSISTANCE_REASONS,
    ASSISTANCE_SUMMARY_MAX_LENGTH,
)
from app.model.guardrail import check_emergency
from app.model.permissions import can_access
from app.model.repositories import assistance as repo
from app.views import messages

from .base import ActionCommand, ActionNotPossible
from .registry import register


def _not_allowed() -> ActionNotPossible:
    # The same refusal whether the older adult doesn't exist or the requester lacks
    # consent for them (plan §5.2).
    return ActionNotPossible("not_allowed", messages.HELP_NOT_ALLOWED)


def _already_requested() -> ActionNotPossible:
    return ActionNotPossible("already_requested", messages.HELP_ALREADY_REQUESTED)


@register
class RequestHelp(ActionCommand):
    action_type = "request_help"
    reversible = False  # a support person may already be on it

    def __init__(self, user: User, payload: dict, **adapters) -> None:
        super().__init__(user, payload, **adapters)
        try:
            self.older_adult_id = uuid.UUID(str(payload.get("older_adult_id", "")))
        except ValueError:
            self.older_adult_id = None
        self.summary_text = str(payload.get("summary") or "").strip()
        self.reason = str(payload.get("reason") or "user_request")

    def summary(self, session: Session) -> str:
        if not self.summary_text:
            return messages.HELP_CONFIRM_NO_SUMMARY
        return messages.HELP_CONFIRM.format(summary=self.summary_text)

    def revalidate(self, session: Session) -> None:
        self._check_allowed(session)
        if self.reason not in ASSISTANCE_REASONS:
            raise ActionNotPossible("invalid_reason", messages.NOT_UNDERSTOOD)
        if len(self.summary_text) > ASSISTANCE_SUMMARY_MAX_LENGTH:
            raise ActionNotPossible("summary_too_long", messages.HELP_SUMMARY_TOO_LONG)
        # Help from a person can take a while: an emergency needs 911, not a queue.
        emergency_message = check_emergency(self.summary_text)
        if emergency_message is not None:
            raise ActionNotPossible("emergency", emergency_message)
        if repo.open_for_user(session, self.older_adult_id) is not None:
            raise _already_requested()

    def execute(self, session: Session) -> dict:
        request = AssistanceRequest(
            user_id=self.older_adult_id,
            requested_by=self.user.id,
            reason=self.reason,
            summary=self.summary_text or None,
            status="open",
        )
        session.add(request)
        try:
            session.flush()  # the unique "one unresolved request" index is the final check
        except IntegrityError:
            raise _already_requested() from None
        return {"assistance_request_id": str(request.id)}

    def success_message(self, result: dict) -> str:
        return messages.HELP_REQUESTED

    def _check_allowed(self, session: Session) -> None:
        if self.older_adult_id is None or session.get(User, self.older_adult_id) is None:
            raise _not_allowed()
        if not can_access(session, self.user, self.older_adult_id, "profile:manage"):
            raise _not_allowed()
