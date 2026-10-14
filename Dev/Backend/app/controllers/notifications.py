"""Reminder delivery to the screen (S2-10, plan §6.4). Sprint 2 uses polling: the frontend
calls GET /notifications every 15-30 s while the app is open."""

import uuid

from fastapi import APIRouter, HTTPException, status

from app.controllers.dependencies import CurrentUser, SessionDep
from app.model.services.appointment_reminders import ReminderAlreadyAnswered, ReminderNotFound
from app.model.services.notifications import appointment_reminders, recent_notifications
from app.views.schemas.notifications import NotificationOut

router = APIRouter(tags=["notifications"])


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(user: CurrentUser, session: SessionDep):
    """Every reminder (appointment and medication) that came due in the last 12 hours,
    with its current status, oldest first. Not-yet-due reminders are not included."""
    return [NotificationOut.from_notification(n) for n in recent_notifications(session, user)]


@router.post("/appointment-reminders/{reminder_id}/acknowledge", response_model=NotificationOut)
def acknowledge_appointment_reminder(
    reminder_id: uuid.UUID, user: CurrentUser, session: SessionDep
):
    """The OK button. 404 not found or not yours · 409 not waiting for an answer."""
    try:
        item = appointment_reminders.acknowledge(session, user, reminder_id)
    except ReminderNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reminder not found") from None
    except ReminderAlreadyAnswered as error:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Reminder is {error.args[0]}, not waiting for an answer"
        ) from None
    session.commit()
    return NotificationOut.from_notification(item)
