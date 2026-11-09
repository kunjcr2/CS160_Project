"""Domain events and a small in-process publisher (Observer, plan §4).

Handlers run synchronously inside the caller's database transaction, so the event and
its side effects (for example, reminder rows for a new booking) commit or roll back
together. Handlers receive the SQLAlchemy session first, then the event.
"""

import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

Handler = Callable[[Session, object], None]


@dataclass(frozen=True)
class ActionExecuted:
    action_id: uuid.UUID
    user_id: uuid.UUID
    action_type: str
    result: dict


class EventPublisher:
    def __init__(self) -> None:
        self._handlers: dict[type, list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: Handler) -> None:
        if handler not in self._handlers[event_type]:  # registering twice is harmless
            self._handlers[event_type].append(handler)

    def publish(self, session: Session, event: object) -> None:
        for handler in self._handlers[type(event)]:
            handler(session, event)


events = EventPublisher()
