"""PB-07: send a non-urgent message to the care team. Send only: replies and read
status are deferred (plan §17).

Payload: {"older_adult_id": "...", "provider_id": "...", "body": "..."}. older_adult_id
is whose data this is about (plan §5.2): the sender may be that older adult, or a
caregiver with "profile:manage" consent for them.
"""

import uuid

from sqlalchemy.orm import Session

from app.adapters.messaging.interface import MessagingUnavailableError
from app.model.entities import Message, Provider, User
from app.model.entities.message import MESSAGE_BODY_MAX_LENGTH
from app.model.guardrail import check_emergency
from app.model.permissions import can_access
from app.views import messages

from .base import ActionCommand, ActionNotPossible
from .registry import register


def _not_allowed() -> ActionNotPossible:
    # Deliberately the same refusal whether the older adult doesn't exist or this
    # sender just lacks consent for them (plan §5.2): never confirm which it is.
    return ActionNotPossible("not_allowed", messages.CARE_MESSAGE_NOT_ALLOWED)


def _recipient_unknown() -> ActionNotPossible:
    return ActionNotPossible("recipient_not_found", messages.CARE_MESSAGE_RECIPIENT_UNKNOWN)


@register
class SendCareMessage(ActionCommand):
    action_type = "send_care_message"
    reversible = False  # a sent message can't be unsent

    def __init__(self, user: User, payload: dict, **adapters) -> None:
        super().__init__(user, payload, **adapters)
        self.body = str(payload.get("body", "")).strip()
        try:
            self.older_adult_id = uuid.UUID(str(payload.get("older_adult_id", "")))
        except ValueError:
            self.older_adult_id = None
        try:
            self.provider_id = uuid.UUID(str(payload.get("provider_id", "")))
        except ValueError:
            self.provider_id = None

    def summary(self, session: Session) -> str:
        provider = self._provider(session)
        return messages.CARE_MESSAGE_CONFIRM.format(doctor=provider.name, body=self.body)

    def revalidate(self, session: Session) -> None:
        self._older_adult(session)
        self._provider(session)
        if not self.body:
            raise ActionNotPossible("empty_message", messages.CARE_MESSAGE_EMPTY)
        if len(self.body) > MESSAGE_BODY_MAX_LENGTH:
            raise ActionNotPossible("message_too_long", messages.CARE_MESSAGE_TOO_LONG)
        emergency_message = check_emergency(self.body)
        if emergency_message is not None:
            raise ActionNotPossible("emergency", emergency_message)

    def execute(self, session: Session) -> dict:
        provider = self._provider(session)
        message = Message(
            sender_id=self.user.id,
            older_adult_id=self.older_adult_id,
            provider_id=provider.id,
            body=self.body,
            status="failed",  # overwritten below if the send succeeds
        )
        session.add(message)
        sender_ref = str(self.user.id)
        try:
            sent = self.messaging.send(provider.external_ref, self.body, sender_ref=sender_ref)
        except MessagingUnavailableError:
            session.flush()
            return {"message_id": str(message.id), "provider_name": provider.name, "ok": False}
        message.status = "sent"
        message.external_ref = sent.external_ref
        session.flush()
        return {"message_id": str(message.id), "provider_name": provider.name, "ok": True}

    def success_message(self, result: dict) -> str:
        if not result["ok"]:
            return messages.CARE_MESSAGE_FAILED.format(doctor=result["provider_name"])
        return messages.CARE_MESSAGE_SENT.format(doctor=result["provider_name"])

    def _older_adult(self, session: Session) -> User:
        if self.older_adult_id is None:
            raise _not_allowed()
        older_adult = session.get(User, self.older_adult_id)
        if older_adult is None:
            raise _not_allowed()
        if not can_access(session, self.user, self.older_adult_id, "profile:manage"):
            raise _not_allowed()
        return older_adult

    def _provider(self, session: Session) -> Provider:
        if self.provider_id is None:
            raise _recipient_unknown()
        provider = session.get(Provider, self.provider_id)
        if provider is None:
            raise _recipient_unknown()
        return provider
