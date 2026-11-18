"""OpenAI function calling and a deterministic offline conversation model."""

import json
import re
from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI


@dataclass(frozen=True)
class ModelResponse:
    reply: str
    proposal: dict[str, object] | None


class LanguageModel(Protocol):
    def respond(self, text: str, language: str) -> ModelResponse: ...


def _tool(name: str, description: str, fields: dict[str, dict]) -> dict:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": fields,
            "required": list(fields),
            "additionalProperties": False,
        },
        "strict": True,
    }


_OPTIONAL = {"type": ["string", "null"]}
TOOLS = [
    _tool(
        "propose_appointment",
        "Identify a request to find or book a doctor appointment. This never books it.",
        {"doctor": _OPTIONAL, "date_hint": _OPTIONAL},
    ),
    _tool(
        "propose_medication_reminder",
        "Identify a request for a medication or dose reminder. This never schedules it.",
        {"medication": _OPTIONAL, "time_hint": _OPTIONAL},
    ),
    _tool(
        "propose_refill",
        "Identify a prescription refill request. This never submits it.",
        {"medication": _OPTIONAL},
    ),
    _tool(
        "propose_human_help",
        "Identify an explicit request to speak with a person or live agent.",
        {"summary": _OPTIONAL},
    ),
]

TOOL_KINDS = {
    "propose_appointment": "appointment",
    "propose_medication_reminder": "medication_reminder",
    "propose_refill": "refill",
    "propose_human_help": "human_help",
}


class OpenAILanguageModel:
    def __init__(
        self, api_key: str, model: str, reasoning_effort: str, max_output_tokens: int
    ) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._reasoning_effort = reasoning_effort
        self._max_output_tokens = max_output_tokens

    def respond(self, text: str, language: str) -> ModelResponse:
        response = self._client.responses.create(
            model=self._model,
            input=text,
            instructions=_instructions(language),
            tools=TOOLS,
            tool_choice="auto",
            parallel_tool_calls=False,
            reasoning={"effort": self._reasoning_effort},
            max_output_tokens=self._max_output_tokens,
            store=False,
        )
        calls = [item for item in response.output if item.type == "function_call"]
        if len(calls) > 1:
            raise ValueError("OpenAI returned multiple tool calls")
        if not calls:
            return ModelResponse(reply=(response.output_text or "").strip(), proposal=None)
        call = calls[0]
        if call.name not in TOOL_KINDS:
            raise ValueError("OpenAI returned an unknown tool")
        try:
            arguments = json.loads(call.arguments)
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError("OpenAI returned invalid tool arguments") from error
        if not isinstance(arguments, dict):
            raise ValueError("OpenAI returned non-object tool arguments")
        return ModelResponse(
            reply="",
            proposal={"kind": TOOL_KINDS[call.name], **arguments},
        )


class FakeLanguageModel:
    """Small, predictable intent fixture for CI and local development."""

    def respond(self, text: str, language: str) -> ModelResponse:
        utterance = text.strip()
        lower = utterance.lower()
        if re.search(r"\b(person|human|agent|representative|persona|agente)\b", lower):
            return ModelResponse("", {"kind": "human_help", "summary": None})
        medication = _medication(utterance)
        if re.search(r"\b(refill|renew|refills|resurtir|resurtido|recarga)\b", lower):
            return ModelResponse("", {"kind": "refill", "medication": medication})
        if re.search(r"\b(appointment|doctor|visit|cita|m[eé]dico|doctora?)\b", lower):
            doctor = re.search(r"\b(?:Dr\.?|Dra\.?)\s+[\w-]+", utterance, re.IGNORECASE)
            date = re.search(
                r"\b(?:next\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
                r"lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)\b|"
                r"\b(?:today|tomorrow|hoy|ma[nñ]ana)\b",
                utterance,
                re.IGNORECASE,
            )
            return ModelResponse(
                "",
                {
                    "kind": "appointment",
                    "doctor": doctor.group() if doctor else None,
                    "date_hint": date.group() if date else None,
                },
            )
        if re.search(r"\b(remind|reminder|medicine|medication|recu[eé]rdame|medicina)\b", lower):
            time = re.search(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b", lower)
            return ModelResponse(
                "",
                {
                    "kind": "medication_reminder",
                    "medication": medication,
                    "time_hint": time.group() if time else None,
                },
            )
        return ModelResponse("", None)


def _medication(text: str) -> str | None:
    match = re.search(
        r"\b(?:my|mi|the|la|el)\s+([A-Za-z][\w-]*)\s+"
        r"(?:medicine|medication|pill|prescription|medicina|pastilla)\b|"
        r"\b(?:take|tomar|for|de|refill|renew|resurtir)\s+"
        r"(?:my|mi|the|la|el)?\s*([A-Za-z][\w-]*)\b",
        text,
        re.IGNORECASE,
    )
    return next((part for part in match.groups() if part), None) if match else None


def build_language_model(
    *, fake_ai: bool, api_key: str | None, model: str, reasoning_effort: str, max_output_tokens: int
) -> LanguageModel:
    if fake_ai:
        return FakeLanguageModel()
    if not api_key:
        raise ValueError("OPENAI_API_KEY must be set")
    return OpenAILanguageModel(api_key, model, reasoning_effort, max_output_tokens)


def _instructions(language: str) -> str:
    return f"""You interpret one utterance for a healthcare assistant. Reply in {language}.
Use exactly one function tool for an appointment, medication reminder, prescription refill,
or explicit request for a human agent. Never infer a medicine, doctor, or date that was not
said. Use null for missing details. The summary for human help must be short, factual, and
contain no full transcript or sensitive medical details. For other requests, give one short
clarifying sentence without a tool. Do not provide medical advice or claim any action
was completed. Tool calls only propose; they do not execute anything."""
