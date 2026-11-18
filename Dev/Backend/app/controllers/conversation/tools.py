"""Validate AI tool arguments before exposing a proposed action to the client."""

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


class RefillProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["refill"] = "refill"
    medication: str | None = Field(default=None, max_length=120)


class HumanHelpProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["human_help"] = "human_help"
    summary: str | None = Field(default=None, max_length=160)


Proposal = Annotated[
    AppointmentProposal | MedicationReminderProposal | RefillProposal | HumanHelpProposal,
    Field(discriminator="kind"),
]


def propose_appointment(doctor: str | None, date_hint: str | None) -> AppointmentProposal:
    return AppointmentProposal(doctor=doctor, date_hint=date_hint)


def propose_medication_reminder(
    medication: str | None, time_hint: str | None
) -> MedicationReminderProposal:
    return MedicationReminderProposal(medication=medication, time_hint=time_hint)


def propose_refill(medication: str | None) -> RefillProposal:
    return RefillProposal(medication=medication)


def propose_human_help(summary: str | None) -> HumanHelpProposal:
    return HumanHelpProposal(summary=summary)


def proposal_from_json(proposal: dict[str, object] | None) -> Proposal | None:
    """Dispatch a tool call to a typed proposal; no action executes here."""
    if proposal is None:
        return None
    kind = proposal.get("kind")
    if kind == "appointment":
        validated = AppointmentProposal.model_validate(proposal)
        return propose_appointment(validated.doctor, validated.date_hint)
    if kind == "medication_reminder":
        validated = MedicationReminderProposal.model_validate(proposal)
        return propose_medication_reminder(validated.medication, validated.time_hint)
    if kind == "refill":
        validated = RefillProposal.model_validate(proposal)
        return propose_refill(validated.medication)
    if kind == "human_help":
        validated = HumanHelpProposal.model_validate(proposal)
        return propose_human_help(validated.summary)
    raise ValueError("Unknown AI tool")
