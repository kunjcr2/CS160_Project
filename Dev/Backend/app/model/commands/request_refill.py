"""PB-04: ask the pharmacy to refill one of the older adult's medications.

Payload: {"older_adult_id": "...", "medication_id": "..."} or, instead of medication_id,
{"medication_name": "my blood pressure pill"} with what the user said; it is matched
against their active medications (refill_service.match_medications), and an unclear
match is refused with a "which one?" question instead of guessing.

older_adult_id is whose medicine this is (plan §5.2): the requester may be that older
adult, or a caregiver with "medications:manage" consent for them.
"""

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.pharmacy.interface import PharmacyUnavailableError
from app.model.entities import Medication, RefillRequest, User
from app.model.permissions import can_access
from app.model.repositories import refills as repo
from app.model.services.refill_service import match_medications
from app.views import messages
from app.views.formatting import spoken_list

from .base import ActionCommand, ActionNotPossible
from .registry import register


def _not_allowed() -> ActionNotPossible:
    # The same refusal whether the older adult doesn't exist or the requester just lacks
    # consent for them (plan §5.2): never confirm which it is.
    return ActionNotPossible("not_allowed", messages.REFILL_NOT_ALLOWED)


def _unknown() -> ActionNotPossible:
    return ActionNotPossible("medication_not_found", messages.REFILL_UNKNOWN_MEDICATION)


def _uuid(value) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


@register
class RequestRefill(ActionCommand):
    action_type = "request_refill"
    reversible = False  # the pharmacy may already be filling it

    def __init__(self, user: User, payload: dict, **adapters) -> None:
        super().__init__(user, payload, **adapters)
        self.older_adult_id = _uuid(payload.get("older_adult_id", ""))
        self.medication_id = _uuid(payload["medication_id"]) if "medication_id" in payload else None
        self.medication_name = str(payload.get("medication_name", "")).strip()

    def summary(self, session: Session) -> str:
        medication = self._medication(session)
        return messages.REFILL_CONFIRM.format(name=medication.name, dosage=medication.dosage)

    def revalidate(self, session: Session) -> None:
        self._check_can_refill(session, self._medication(session))

    def execute(self, session: Session) -> dict:
        medication = repo.lock_medication(session, self._medication(session).id)
        self._check_can_refill(session, medication)

        medication.refills_remaining -= 1
        request = RefillRequest(
            user_id=medication.user_id,
            requested_by=self.user.id,
            medication_id=medication.id,
            status="requested",
        )
        session.add(request)
        try:
            session.flush()  # the unique "one open request" index is the final check
        except IntegrityError:
            raise self._already_requested(medication) from None

        try:
            submission = self.pharmacy.submit_refill(
                medication.name, medication.dosage, patient_ref=str(medication.user_id)
            )
        except PharmacyUnavailableError:
            # Raising rolls back the savepoint, so the refill count is untouched.
            raise ActionNotPossible("pharmacy_unavailable", messages.REFILL_FAILED) from None
        request.external_ref = submission.external_ref
        session.flush()
        return {
            "refill_request_id": str(request.id),
            "medication_name": medication.name,
            "refills_remaining": medication.refills_remaining,
        }

    def success_message(self, result: dict) -> str:
        return messages.REFILL_REQUESTED.format(name=result["medication_name"])

    def _older_adult_id(self, session: Session) -> uuid.UUID:
        if self.older_adult_id is None or session.get(User, self.older_adult_id) is None:
            raise _not_allowed()
        if not can_access(session, self.user, self.older_adult_id, "medications:manage"):
            raise _not_allowed()
        return self.older_adult_id

    def _medication(self, session: Session) -> Medication:
        older_adult_id = self._older_adult_id(session)
        if self.medication_id is not None:
            medication = session.get(Medication, self.medication_id)
            if (
                medication is None
                or medication.user_id != older_adult_id
                or medication.stopped_at is not None
            ):
                raise _unknown()
            return medication
        matches = match_medications(session, older_adult_id, self.medication_name)
        if not matches:
            raise _unknown()
        if len(matches) > 1:
            names = spoken_list([m.name for m in matches])
            raise ActionNotPossible(
                "medication_unclear", messages.REFILL_WHICH_ONE.format(options=names)
            )
        return matches[0]

    def _check_can_refill(self, session: Session, medication: Medication) -> None:
        if repo.open_request(session, medication.id) is not None:
            raise self._already_requested(medication)
        if medication.refills_remaining <= 0:
            raise ActionNotPossible(
                "no_refills", messages.REFILL_NONE_LEFT.format(name=medication.name)
            )

    @staticmethod
    def _already_requested(medication: Medication) -> ActionNotPossible:
        return ActionNotPossible(
            "already_requested", messages.REFILL_ALREADY_REQUESTED.format(name=medication.name)
        )
