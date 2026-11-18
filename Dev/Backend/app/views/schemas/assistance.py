"""JSON shapes for the PB-06 support queue."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.model.entities import AssistanceRequest, User


class AssistanceOut(BaseModel):
    id: uuid.UUID
    older_adult_id: uuid.UUID
    older_adult_name: str  # preferred name if set, e.g. "Maggie (Margaret Lee)"
    reason: str  # user_request, repeated_failures
    summary: str | None  # what they were trying to do, as they agreed to share it
    status: str  # open, in_progress, resolved
    assigned_to_name: str | None
    created_at: datetime
    resolved_at: datetime | None

    @classmethod
    def from_entity(
        cls, request: AssistanceRequest, older_adult: User, agent: User | None
    ) -> "AssistanceOut":
        name = older_adult.display_name
        if older_adult.preferred_name:
            name = f"{older_adult.preferred_name} ({name})"
        return cls(
            id=request.id,
            older_adult_id=request.user_id,
            older_adult_name=name,
            reason=request.reason,
            summary=request.summary,
            status=request.status,
            assigned_to_name=agent.display_name if agent else None,
            created_at=request.created_at,
            resolved_at=request.resolved_at,
        )


class UpdateAssistanceIn(BaseModel):
    status: Literal["in_progress", "resolved"]
