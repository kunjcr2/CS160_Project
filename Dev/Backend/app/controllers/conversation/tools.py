"""Validated proposal types exposed by the conversation controller."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class AppointmentProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["appointment"] = "appointment"
    doctor: str | None = Field(default=None, max_length=120)
    date_hint: str | None = Field(default=None, max_length=80)


class MedicationReminderProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["medication_reminder"] = "medication_reminder"
    medication: str | None = Field(default=None, max_length=120)
    time_hint: str | None = Field(default=None, max_length=80)


Proposal = Annotated[AppointmentProposal | MedicationReminderProposal, Field(discriminator="kind")]


def proposal_from_json(proposal: dict[str, object] | None) -> Proposal | None:
    if proposal is None:
        return None
    if proposal.get("kind") == "appointment":
        return AppointmentProposal.model_validate(proposal)
    if proposal.get("kind") == "medication_reminder":
        return MedicationReminderProposal.model_validate(proposal)
    return None
