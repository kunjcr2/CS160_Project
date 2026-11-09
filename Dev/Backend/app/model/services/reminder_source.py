"""The interface every reminder type implements (plan §6.3, §6.4).

The reminder worker calls send_due() and follow_up() for every source about every 30 s;
GET /notifications calls recent_for_user() for every source. To add a reminder type
(PB-03 medication reminders), implement ReminderSource and add an instance to SOURCES in
app/model/services/notifications.py. Nothing else changes.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.model.entities import User


@dataclass(frozen=True)
class Notification:
    """One reminder as the screen shows it."""

    kind: str  # "appointment_reminder", "medication_reminder"
    id: str
    due_at: datetime  # UTC
    status: str  # the reminder's current status; buttons only when "sent"
    message: str  # the sentence to show and speak, in the user's time zone
    fields: dict[str, Any] = field(default_factory=dict)  # kind-specific extra fields


class ReminderSource(Protocol):
    kind: str

    def send_due(self, session: Session, now: datetime) -> int:
        """Claim reminders due at `now` with SELECT … FOR UPDATE SKIP LOCKED (so two
        workers never send the same one), mark them `sent`, and return how many."""
        ...

    def follow_up(self, session: Session, now: datetime) -> int:
        """Handle sent reminders nobody answered (e.g. re-prompt once, then `missed`).
        Return how many changed."""
        ...

    def recent_for_user(
        self, session: Session, user: User, since: datetime, now: datetime
    ) -> list[Notification]:
        """The user's reminders that came due between `since` and `now`, any status
        except not-yet-sent."""
        ...
