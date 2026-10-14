"""Confirmation endpoints (plan §5.3, §10). Every action that changes the outside world is
executed only through POST /actions/{id}/confirm.

Errors use `detail: {"code": ..., "message": ...}`; `message` is safe to show the user.
"""

import uuid
from datetime import timedelta

from fastapi import APIRouter, HTTPException, status

from app.config import settings
from app.controllers.dependencies import CurrentUser, SessionDep
from app.model.commands import ActionNotPossible, UnknownActionType
from app.model.services.action_service import ActionNotFound, ActionNotPending, ActionService
from app.views import messages
from app.views.schemas.actions import ActionOut, ActionOutcomeOut, PendingActionOut, ProposeActionIn

router = APIRouter(prefix="/actions", tags=["actions"])


def _service(session) -> ActionService:
    return ActionService(session, ttl=timedelta(minutes=settings.pending_action_ttl_minutes))


def _not_found() -> HTTPException:
    return HTTPException(
        status.HTTP_404_NOT_FOUND, {"code": "not_found", "message": messages.ACTION_NOT_PENDING}
    )


@router.post("", response_model=ActionOut, status_code=status.HTTP_201_CREATED)
def propose_action(body: ProposeActionIn, user: CurrentUser, session: SessionDep) -> ActionOut:
    """Create a proposal to read back to the user. This never executes anything.

    The conversation controller proposes actions itself; this endpoint lets the frontend
    and manual tests do the same without the AI. A new proposal replaces the old one.
    """
    try:
        action = _service(session).propose(user, body.action_type, body.payload)
    except UnknownActionType:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"code": "unknown_action_type", "message": messages.NOT_UNDERSTOOD},
        ) from None
    except ActionNotPossible as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT, {"code": error.code, "message": error.message}
        ) from None
    session.commit()
    return ActionOut.from_entity(action)


@router.get("/pending", response_model=PendingActionOut)
def get_pending_action(user: CurrentUser, session: SessionDep) -> PendingActionOut:
    action = _service(session).get_pending(user)
    session.commit()  # saves an `expired` status if the proposal just timed out
    return PendingActionOut(action=ActionOut.from_entity(action) if action else None)


@router.post("/{action_id}/confirm", response_model=ActionOutcomeOut)
def confirm_action(action_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    """The user said yes. Safe to call twice: it never executes twice.

    200 with status `executed` or `failed` (the message explains the failure) ·
    404 not found or not yours · 409 cancelled, replaced, or expired.
    """
    try:
        outcome = _service(session).confirm(action_id, user)
    except ActionNotFound:
        raise _not_found() from None
    except ActionNotPending as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT, {"code": error.action.status, "message": error.message}
        ) from None
    session.commit()
    if outcome.action.status == "expired":
        raise HTTPException(
            status.HTTP_409_CONFLICT, {"code": "expired", "message": outcome.message}
        )
    return ActionOutcomeOut(action=ActionOut.from_entity(outcome.action), message=outcome.message)


@router.post("/{action_id}/cancel", response_model=ActionOutcomeOut)
def cancel_action(action_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    """The user said no. 404 not found or not yours · 409 already executed, failed, or
    expired."""
    try:
        outcome = _service(session).cancel(action_id, user)
    except ActionNotFound:
        raise _not_found() from None
    except ActionNotPending as error:
        session.commit()  # keep an `expired` status set while checking
        raise HTTPException(
            status.HTTP_409_CONFLICT, {"code": error.action.status, "message": error.message}
        ) from None
    session.commit()
    return ActionOutcomeOut(action=ActionOut.from_entity(outcome.action), message=outcome.message)
