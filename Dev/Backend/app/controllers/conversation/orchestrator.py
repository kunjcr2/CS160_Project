"""Turn an utterance into a safe, typed proposal; never execute an action."""

from dataclasses import dataclass

from pydantic import ValidationError

from app.adapters.llm.client import LanguageModel
from app.controllers.conversation.tools import Proposal, proposal_from_json
from app.views import messages


@dataclass(frozen=True)
class ConversationResult:
    reply: str
    proposal: Proposal | None
    readback: str | None = None
    language: str = "en"
    unclear_turns: int = 0
    offer_human_help: bool = False


class ConversationOrchestrator:
    def __init__(self, language_model: LanguageModel) -> None:
        self._language_model = language_model

    def process(self, text: str, language: str, unclear_turns: int = 0) -> ConversationResult:
        language = language.split("-")[0].lower()
        if language not in ("en", "es"):
            language = "en"
        if unclear_turns >= 3 and text.strip().lower() in ("yes", "yes please", "sí", "si"):
            return ConversationResult(
                reply=messages.say("human_help_requested", language),
                proposal=proposal_from_json({"kind": "human_help", "summary": None}),
                language=language,
            )
        try:
            model_response = self._language_model.respond(text, language)
            proposal = proposal_from_json(model_response.proposal)
        except (ValidationError, ValueError, TypeError):
            return self._unclear(language, unclear_turns)

        if proposal is None:
            return self._unclear(language, unclear_turns)

        kind = proposal.kind
        readback = None
        if kind == "appointment":
            if not proposal.doctor:
                key = "appointment_missing_doctor"
            elif not proposal.date_hint:
                key = "appointment_missing_date"
            else:
                key = "appointment_ready"
                readback = messages.say(
                    "appointment_readback",
                    language,
                    doctor=proposal.doctor,
                    date_hint=proposal.date_hint,
                )
        elif kind == "medication_reminder":
            if not proposal.medication:
                key = "medication_missing_name"
            elif not proposal.time_hint:
                key = "medication_missing_time"
            else:
                key = "medication_ready"
                readback = messages.say(
                    "medication_readback",
                    language,
                    medication=proposal.medication,
                    time_hint=proposal.time_hint,
                )
        elif kind == "refill":
            key = "refill_ready" if proposal.medication else "refill_missing_name"
            if proposal.medication:
                readback = messages.say("refill_readback", language, medication=proposal.medication)
        else:
            key = "human_help"
        reply = model_response.reply or messages.say(
            key, language, medication=getattr(proposal, "medication", "")
        )
        return ConversationResult(
            reply=reply, proposal=proposal, readback=readback, language=language
        )

    @staticmethod
    def _unclear(language: str, previous: int) -> ConversationResult:
        failures = min(previous + 1, 3)
        offer = failures >= 3
        return ConversationResult(
            reply=messages.say("offer_human_help" if offer else "not_understood", language),
            proposal=None,
            language=language,
            unclear_turns=failures,
            offer_human_help=offer,
        )
