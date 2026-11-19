"""PB-06 support queue: what support agents see and do with help requests.

Creating a request is the RequestHelp command (confirmed by the user, plan §5.3). This
service is for the agent side only. Nothing here commits; the caller does.
"""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.model.entities import AssistanceRequest, User
from app.model.repositories import assistance as repo

AGENT_ROLES = ("support_agent", "admin")

# Which status an agent may move a request to, from each status.
_ALLOWED = {
    "open": ("in_progress", "resolved"),
    "in_progress": ("resolved",),
    "resolved": (),
}


class NotAnAgentError(Exception):
    """Only support agents (and admins) see and change the queue."""


class AssistanceNotFoundError(Exception):
    pass


class AssistanceNotChangeableError(Exception):
    """E.g. resolving a request that is already resolved."""

    def __init__(self, request: AssistanceRequest) -> None:
        super().__init__(request.status)
        self.request = request


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _require_agent(user: User) -> None:
    if user.role not in AGENT_ROLES:
        raise NotAnAgentError(user.role)


def queue(session: Session, agent: User) -> list[AssistanceRequest]:
    _require_agent(agent)
    return repo.queue(session)


def update_status(
    session: Session,
    agent: User,
    request_id: uuid.UUID,
    new_status: str,
    *,
    clock: Callable[[], datetime] = _utcnow,
) -> AssistanceRequest:
    """Take a request (`in_progress`, assigned to this agent) or close it (`resolved`)."""
    _require_agent(agent)
    request = repo.lock(session, request_id)
    if request is None:
        raise AssistanceNotFoundError(request_id)
    if request.status == new_status and new_status == "in_progress":
        if request.assigned_to == agent.id:
            return request  # taking it twice is harmless
        raise AssistanceNotChangeableError(request)  # another agent already has it
    if new_status not in _ALLOWED[request.status]:
        raise AssistanceNotChangeableError(request)
    request.status = new_status
    if request.assigned_to is None or new_status == "in_progress":
        request.assigned_to = agent.id
    if new_status == "resolved":
        request.resolved_at = clock()
    session.flush()
    return request
