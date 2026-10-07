"""Validated proposal types exposed by the conversation controller."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.adapters.llm.client import ToolCall


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


def proposal_from_tool_call(call: ToolCall | None) -> Proposal | None:
    if call is None:
        return None
    if call.name == "propose_appointment_request":
        return AppointmentProposal.model_validate({"kind": "appointment", **call.arguments})
    if call.name == "propose_medication_reminder":
        return MedicationReminderProposal.model_validate(
            {"kind": "medication_reminder", **call.arguments}
        )
    return None
