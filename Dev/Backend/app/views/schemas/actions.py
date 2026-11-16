"""Pending action (confirmation card) request/response models."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.model.entities import PendingAction


class ProposeActionIn(BaseModel):
    action_type: str = Field(examples=["book_appointment"])
    payload: dict[str, Any] = Field(examples=[{"slot_id": "..."}])


class ActionOut(BaseModel):
    id: uuid.UUID
    action_type: str
    summary_text: str  # read back to the user, ends with the question
    status: str  # proposed, executed, failed, cancelled, expired
    expires_at: datetime  # UTC
    result: dict[str, Any] | None = None  # e.g. {"appointment_id": ...} once executed

    @classmethod
    def from_entity(cls, action: PendingAction) -> "ActionOut":
        stored = action.result or {}
        return cls(
            id=action.id,
            action_type=action.action_type,
            summary_text=action.summary_text,
            status=action.status,
            expires_at=action.expires_at,
            result=stored.get("data"),
        )


class ActionOutcomeOut(BaseModel):
    action: ActionOut
    message: str  # the sentence to show and speak


class PendingActionOut(BaseModel):
    action: ActionOut | None  # null when nothing is waiting for an answer
