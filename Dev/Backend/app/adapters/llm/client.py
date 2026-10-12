"""OpenAI Structured Outputs adapter for the conversation controller."""

import json
from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI


@dataclass(frozen=True)
class ModelResponse:
    reply: str
    proposal: dict[str, object] | None


class LanguageModel(Protocol):
    def respond(self, text: str, language: str) -> ModelResponse: ...


RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "proposal": {
            "anyOf": [
                {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": ["appointment"]},
                        "doctor": {"type": ["string", "null"]},
                        "date_hint": {"type": ["string", "null"]},
                    },
                    "required": ["kind", "doctor", "date_hint"],
                    "additionalProperties": False,
                },
                {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": ["medication_reminder"]},
                        "medication": {"type": ["string", "null"]},
                        "time_hint": {"type": ["string", "null"]},
                    },
                    "required": ["kind", "medication", "time_hint"],
                    "additionalProperties": False,
                },
                {"type": "null"},
            ]
        },
    },
    "required": ["reply", "proposal"],
    "additionalProperties": False,
}


class OpenAILanguageModel:
    def __init__(self, api_key: str, model: str, reasoning_effort: str, max_output_tokens: int) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._reasoning_effort = reasoning_effort
        self._max_output_tokens = max_output_tokens

    def respond(self, text: str, language: str) -> ModelResponse:
        response = self._client.responses.create(
            model=self._model,
            input=text,
            instructions=_instructions(language),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "conversation_response",
                    "strict": True,
                    "schema": RESPONSE_SCHEMA,
                }
            },
            reasoning={"effort": self._reasoning_effort},
            max_output_tokens=self._max_output_tokens,
            store=False,
        )
        try:
            payload = json.loads(response.output_text)
        except json.JSONDecodeError as error:
            raise ValueError("OpenAI returned invalid structured JSON") from error
        if not isinstance(payload, dict):
            raise ValueError("OpenAI returned a non-object structured response")

        reply = payload.get("reply")
        proposal = payload.get("proposal")
        if not isinstance(reply, str) or (proposal is not None and not isinstance(proposal, dict)):
            raise ValueError("OpenAI returned an invalid structured response")
        return ModelResponse(reply=reply, proposal=proposal)


def build_language_model(
    *, api_key: str | None, model: str, reasoning_effort: str, max_output_tokens: int
) -> LanguageModel:
    if not api_key:
        raise ValueError("OPENAI_API_KEY must be set")
    return OpenAILanguageModel(api_key, model, reasoning_effort, max_output_tokens)


def _instructions(language: str) -> str:
    return f"""You are a helpful healthcare-assistant conversation turn.

The user's language is {language}. Do not provide medical advice. Return only the
JSON object required by the response schema; never use Markdown or add extra keys.

For a request to book, schedule, find, or change a doctor appointment, set proposal.kind
to appointment. For a medication or dose reminder, set proposal.kind to
medication_reminder. For any other request, set proposal to null.

Extract only facts explicitly stated by the user. Never invent a doctor, date, medication,
time, or frequency. Use null only for a tool argument the user did not state. Preserve
the user's wording for names and date/time phrases.

Set reply to one short, natural sentence. For an appointment proposal, ask only for the
missing doctor or date. If both are present, acknowledge the request without claiming it
was created, changed, booked, or confirmed. For a medication reminder proposal, ask only
for missing medication or time. For proposal null, briefly say you did not understand."""
