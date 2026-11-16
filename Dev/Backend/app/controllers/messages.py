"""Care-team messaging endpoint (PB-07, send only, plan §10). Sending goes through
/actions, like every other state-changing operation (plan §5.3); this router only
reads back what was sent.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.controllers.dependencies import Db, require_access
from app.model.entities import Provider
from app.model.repositories import messages as repo
from app.views.schemas.messages import MessageOut

router = APIRouter(tags=["messages"])

CanRead = Annotated[uuid.UUID, Depends(require_access("profile:manage"))]


@router.get("/older-adults/{older_adult_id}/messages", response_model=list[MessageOut])
def list_messages(older_adult_id: CanRead, db: Db) -> list[MessageOut]:
    """This older adult's sent messages, newest first (same consent rules as the
    SendCareMessage command: not allowed -> 404)."""
    return [
        MessageOut.from_entity(message, db.get(Provider, message.provider_id))
        for message in repo.for_older_adult(db, older_adult_id)
    ]
