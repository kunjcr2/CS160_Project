"""Reminder worker (SR-07, plan §6.3). Sends due reminders even when nobody is making a
request. Safe to run more than once at the same time: rows are claimed with
FOR UPDATE SKIP LOCKED, so each reminder is sent exactly once.

Run from Dev/Backend:  python -m app.workers.reminders
(or set RUN_REMINDER_WORKER=true to run it inside the API process instead)
"""

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.model.services.notifications import SOURCES

log = logging.getLogger(__name__)


def run_once(
    session_factory: Callable[[], Session] = SessionLocal, now: datetime | None = None
) -> dict[str, int]:
    """One pass over every reminder type. Each type commits on its own, so a failure in
    one doesn't stop the others. Returns how many reminders each type sent."""
    now = now or datetime.now(UTC)
    sent = {}
    for source in SOURCES:
        with session_factory() as session:
            try:
                sent[source.kind] = source.send_due(session, now)
                source.follow_up(session, now)
                session.commit()
            except Exception:
                session.rollback()
                log.exception("Reminder source %s failed", source.kind)
                sent[source.kind] = 0
    return sent


def run_forever(stop: threading.Event | None = None) -> None:
    stop = stop or threading.Event()
    log.info("Reminder worker started (every %s s)", settings.reminder_poll_seconds)
    while not stop.is_set():
        sent = run_once()
        if any(sent.values()):
            log.info("Sent reminders: %s", sent)
        stop.wait(settings.reminder_poll_seconds)


def start_in_background() -> threading.Event:
    """Run the worker in a daemon thread; set the returned event to stop it."""
    stop = threading.Event()
    threading.Thread(target=run_forever, args=(stop,), name="reminder-worker", daemon=True).start()
    return stop


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        run_forever()
    except KeyboardInterrupt:
        pass  # exit quietly on Ctrl+C
