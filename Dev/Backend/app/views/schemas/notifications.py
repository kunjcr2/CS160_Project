"""Reminder notifications for the banner (S2-10, S2-16). The frontend polls
GET /notifications every 15-30 s and shows Taken/Missed or OK buttons when status is "sent".
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.model.services.reminder_source import Notification


class NotificationOut(BaseModel):
    """Common fields. Each kind adds its own fields (see the examples at /docs):

    appointment_reminder: timing (day_before, morning_of, hour_before), appointment_id,
    provider_name, starts_at, location. Status: sent → acknowledged (OK button).
    """

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "example": {
                "kind": "appointment_reminder",
                "id": "3f2c9a7e-0000-0000-0000-000000000000",
                "due_at": "2026-10-19T17:30:00Z",
                "status": "sent",
                "message": "Reminder: you see Dr. Lisa Chen tomorrow at 10:30 AM, at Valley "
                "Medical.",
                "timing": "day_before",
                "appointment_id": "8d1e5b2c-0000-0000-0000-000000000000",
                "provider_name": "Dr. Lisa Chen",
                "starts_at": "2026-10-20T17:30:00Z",
                "location": "Valley Medical",
            }
        },
    )

    kind: str
    id: str
    due_at: datetime  # UTC; show in the user's local time
    status: str
    message: str  # the sentence to show and speak

    @classmethod
    def from_notification(cls, item: Notification) -> "NotificationOut":
        return cls(
            kind=item.kind,
            id=item.id,
            due_at=item.due_at,
            status=item.status,
            message=item.message,
            **item.fields,
        )
