"""PB-06 support queue (plan §10), for support agents. Asking for help goes through
/actions (`request_help`), so the user confirms first (plan §5.3).

403 for anyone who isn't a support agent or admin.
"""

import uuid

from fastapi import APIRouter, HTTPException, status

from app.controllers.dependencies import CurrentUser, Db
from app.model.entities import AssistanceRequest, User
from app.model.services import assistance_service as service
from app.views.schemas.assistance import AssistanceOut, UpdateAssistanceIn

router = APIRouter(prefix="/assistance", tags=["assistance"])


def _out(db, request: AssistanceRequest) -> AssistanceOut:
    agent = db.get(User, request.assigned_to) if request.assigned_to else None
    return AssistanceOut.from_entity(request, db.get(User, request.user_id), agent)


def _agents_only() -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, "Support agents only.")


@router.get("/queue", response_model=list[AssistanceOut])
def read_queue(user: CurrentUser, db: Db) -> list[AssistanceOut]:
    """Unresolved help requests, oldest first."""
    try:
        requests = service.queue(db, user)
    except service.NotAnAgentError:
        raise _agents_only() from None
    return [_out(db, request) for request in requests]


@router.patch("/{request_id}", response_model=AssistanceOut)
def update_request(
    request_id: uuid.UUID, body: UpdateAssistanceIn, user: CurrentUser, db: Db
) -> AssistanceOut:
    """Take a request (`in_progress`) or close it (`resolved`). 409 if it can't move
    there, e.g. it's already resolved or another agent has it."""
    try:
        request = service.update_status(db, user, request_id, body.status)
    except service.NotAnAgentError:
        raise _agents_only() from None
    except service.AssistanceNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Help request not found.") from None
    except service.AssistanceNotChangeableError as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            {"code": error.request.status, "message": "This request can't be changed that way."},
        ) from None
    db.commit()
    return _out(db, request)
