"""JSON shape for care-team messages (PB-07, send only)."""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.model.entities import Message, Provider
from app.views.schemas.appointments import ProviderOut


class MessageOut(BaseModel):
    id: uuid.UUID
    provider: ProviderOut
    body: str
    status: str  # sent, failed
    created_at: datetime

    @classmethod
    def from_entity(cls, message: Message, provider: Provider) -> "MessageOut":
        return cls(
            id=message.id,
            provider=ProviderOut.from_entity(provider),
            body=message.body,
            status=message.status,
            created_at=message.created_at,
        )
