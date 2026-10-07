"""Language-model adapters used only by the conversation controller.

Adapters return a requested tool name and JSON-shaped arguments.  They never
execute a tool or access the database.
"""

import json
import re
from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, object]


class LanguageModel(Protocol):
    def choose_tool(self, text: str, language: str) -> ToolCall | None: ...


TOOLS = [
    {
        "type": "function",
        "name": "propose_appointment_request",
        "description": (
            "Use only when the user wants to book, schedule, find, or change a doctor appointment. "
            "This only proposes a slot search; it never books, changes, or confirms an appointment."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "doctor": {
                    "type": ["string", "null"],
                    "description": (
                        "Doctor name stated by the user, including 'Dr.' when stated; otherwise null."
                    ),
                },
                "date_hint": {
                    "type": ["string", "null"],
                    "description": (
                        "Date or relative-date phrase stated by the user, such as 'next Tuesday'; "
                        "otherwise null."
                    ),
                },
            },
            "required": ["doctor", "date_hint"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "propose_medication_reminder",
        "description": (
            "Use only when the user wants a medication or dose reminder. "
            "This only proposes a reminder; it never creates, schedules, or confirms one."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "medication": {
                    "type": ["string", "null"],
                    "description": "Medication name stated by the user; otherwise null.",
                },
                "time_hint": {
                    "type": ["string", "null"],
                    "description": (
                        "Time or frequency stated by the user, such as '8 PM' or 'every morning'; "
                        "otherwise null."
                    ),
                },
            },
            "required": ["medication", "time_hint"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


class FakeLanguageModel:
    """Deterministic local stand-in for tests and development without an API key."""

    def choose_tool(self, text: str, language: str) -> ToolCall | None:
        normalized = text.lower()
        if any(word in normalized for word in ("appointment", "doctor", "schedule", "book")):
            doctor = _doctor_from(text)
            date_hint = _date_hint_from(text)
            return ToolCall("propose_appointment_request", _without_none(doctor=doctor, date_hint=date_hint))
        if any(word in normalized for word in ("medication", "medicine", "pill", "dose", "remind")):
            medication = _medication_from(text)
            time_hint = _time_hint_from(text)
            return ToolCall(
                "propose_medication_reminder", _without_none(medication=medication, time_hint=time_hint)
            )
        return None


class OpenAILanguageModel:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def choose_tool(self, text: str, language: str) -> ToolCall | None:
        response = self._client.responses.create(
            model=self._model,
            input=text,
            instructions=_instructions(language),
            tools=TOOLS,
            tool_choice="auto",
            parallel_tool_calls=False,
            store=False,
        )
        for item in response.output:
            if item.type == "function_call":
                try:
                    arguments = json.loads(item.arguments)
                except json.JSONDecodeError:
                    return None
                return ToolCall(item.name, arguments)
        return None


def build_language_model(*, fake_ai: bool, api_key: str | None, model: str) -> LanguageModel:
    if fake_ai:
        return FakeLanguageModel()
    if not api_key:
        raise ValueError("OPENAI_API_KEY must be set when FAKE_AI is false")
    return OpenAILanguageModel(api_key, model)


def _instructions(language: str) -> str:
    return f"""You are the intent-and-slot extraction component of a healthcare assistant.

The user's language is {language}. Do not provide medical advice. Do not write a
conversational answer.
Your only output is either one function call or no function call.

Call propose_appointment_request when the user asks to book, schedule, find, or change
a doctor appointment.
Call propose_medication_reminder when the user asks to be reminded about a medication
or dose.
For any other request, make no function call.

Extract only facts explicitly stated by the user. Never invent a doctor, date, medication,
time, or frequency. Use null for any tool argument the user did not state. Preserve the
user's wording for names and date/time phrases.

These are proposals only. Never claim that an appointment or reminder was created,
changed, booked, or confirmed."""


def _without_none(**values: str | None) -> dict[str, object]:
    return {key: value for key, value in values.items() if value is not None}


def _doctor_from(text: str) -> str | None:
    match = re.search(r"\b(?:dr\.?|doctor)\s+([A-Z][a-z]+)", text, re.I)
    return f"Dr. {match.group(1)}" if match else None


def _date_hint_from(text: str) -> str | None:
    match = re.search(r"\b(today|tomorrow|next\s+(?:monday|tuesday|wednesday|thursday|friday|week))\b", text, re.I)
    return match.group(1).lower() if match else None


def _medication_from(text: str) -> str | None:
    match = re.search(r"(?:for|about|my)\s+([A-Za-z][A-Za-z -]{1,40}?)(?:\s+(?:at|every|reminder|medicine|medication|pill)|[?.!]|$)", text, re.I)
    return match.group(1).strip() if match else None


def _time_hint_from(text: str) -> str | None:
    match = re.search(r"\b(?:at\s+)?(\d{1,2}(?::\d{2})?\s*(?:a\.m\.|p\.m\.|am|pm)|morning|evening|night)\b", text, re.I)
    return match.group(1).lower() if match else None
