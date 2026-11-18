"""PB-04 refills: find which medication the user means, and keep request statuses up to
date. Submitting a refill is the RequestRefill command, so it only happens after a yes
(plan §5.3). Nothing here commits; the caller does.
"""

import logging
import re
import uuid

from sqlalchemy.orm import Session

from app.adapters.pharmacy.interface import (
    REFILL_PROGRESS,
    PharmacyProvider,
    PharmacyUnavailableError,
)
from app.model.entities import Medication, RefillRequest
from app.model.entities.refill_request import OPEN_REFILL_STATUSES
from app.model.repositories import refills as repo

log = logging.getLogger(__name__)

# Words that say nothing about WHICH medicine ("my blood pressure pill" -> blood, pressure).
_FILLER = {
    "a", "an", "the", "my", "for", "of", "to", "and", "i", "me", "please",
    "pill", "pills", "tablet", "tablets", "medicine", "medicines", "medication",
    "medications", "meds", "prescription", "refill", "refills", "need", "more",
}  # fmt: skip


def _words(text: str | None) -> set[str]:
    return set(re.findall(r"[a-z]+", (text or "").lower())) - _FILLER


def match_medications(session: Session, older_adult_id: uuid.UUID, said: str) -> list[Medication]:
    """The active medications that `said` could mean, best matches only.

    A medicine NAME match ("metformin") wins over a match on its instructions
    ("blood pressure" -> "For blood pressure"). Several results mean: ask which one.
    """
    wanted = _words(said)
    if not wanted:
        return []
    medications = repo.active_medications(session, older_adult_id)
    by_name = [m for m in medications if wanted & _words(m.name)]
    if by_name:
        return by_name
    return [m for m in medications if wanted & _words(m.instructions)]


def refresh_statuses(
    session: Session, requests: list[RefillRequest], pharmacy: PharmacyProvider
) -> None:
    """Ask the pharmacy how each open request is doing, and save any progress.

    A status only ever moves forward. If the pharmacy is down, or doesn't know a request
    (the mock forgets on restart), the last saved status is kept.
    """
    for request in requests:
        if request.status not in OPEN_REFILL_STATUSES or not request.external_ref:
            continue
        try:
            latest = pharmacy.refill_status(request.external_ref)
        except PharmacyUnavailableError:
            log.warning("Pharmacy unavailable; keeping saved refill statuses")
            return
        if latest in REFILL_PROGRESS and (
            REFILL_PROGRESS.index(latest) > REFILL_PROGRESS.index(request.status)
        ):
            request.status = latest
    session.flush()


def list_refills(
    session: Session, older_adult_id: uuid.UUID, pharmacy: PharmacyProvider
) -> list[RefillRequest]:
    """This older adult's refill requests, newest first, with up-to-date statuses."""
    requests = repo.for_older_adult(session, older_adult_id)
    refresh_statuses(session, requests, pharmacy)
    return requests
