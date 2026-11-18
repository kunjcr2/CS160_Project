"""JSON shapes for medications and medication reminders (PB-03)."""

import uuid
from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.model.entities.medication import EVERY_DAY


class ScheduleIn(BaseModel):
    """One time to take the medicine, in the older adult's LOCAL time."""

    time_of_day: time = Field(examples=["08:00"])
    # 0 = Monday ... 6 = Sunday. Leave out for every day.
    days_of_week: list[int] = Field(default_factory=lambda: list(EVERY_DAY), examples=[[0, 2, 4]])

    @field_validator("days_of_week")
    @classmethod
    def valid_days(cls, value: list[int]) -> list[int]:
        if not value or any(day not in EVERY_DAY for day in value):
            raise ValueError("Days must be numbers from 0 (Monday) to 6 (Sunday).")
        return sorted(set(value))


class CreateMedicationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100, examples=["Metformin"])
    dosage: str = Field(min_length=1, max_length=50, examples=["500 mg"])
    instructions: str | None = Field(default=None, max_length=300, examples=["Take with food"])
    refills_remaining: int = Field(default=0, ge=0, le=99)
    schedules: list[ScheduleIn] = Field(
        min_length=1, max_length=8, examples=[[{"time_of_day": "08:00"}, {"time_of_day": "20:00"}]]
    )

    @field_validator("schedules")
    @classmethod
    def no_duplicate_times(cls, value: list[ScheduleIn]) -> list[ScheduleIn]:
        times = [schedule.time_of_day for schedule in value]
        if len(times) != len(set(times)):
            raise ValueError("The same time is listed twice.")
        return value


class ScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    time_of_day: time
    days_of_week: list[int]


class MedicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    dosage: str
    instructions: str | None
    refills_remaining: int
    stopped_at: datetime | None
    schedules: list[ScheduleResponse]


class MedicationReminderResponse(BaseModel):
    """One dose, as the app shows it. Buttons (Taken / Missed) only when status is "sent"."""

    id: uuid.UUID
    medication_id: uuid.UUID
    medication_name: str
    dosage: str
    due_at: datetime  # UTC; the app shows it in the user's time zone
    status: str
    attempts: int  # 2 = this is the re-prompt
    confirmed_at: datetime | None
