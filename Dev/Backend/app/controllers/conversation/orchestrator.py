"""Turn an utterance into a safe, typed proposal; never execute an action."""

from dataclasses import dataclass

from pydantic import ValidationError

from app.adapters.llm.client import LanguageModel
from app.controllers.conversation.tools import Proposal, proposal_from_tool_call
from app.views import messages


@dataclass(frozen=True)
class ConversationResult:
    reply: str
    proposal: Proposal | None


class ConversationOrchestrator:
    def __init__(self, language_model: LanguageModel) -> None:
        self._language_model = language_model

    def process(self, text: str, language: str) -> ConversationResult:
        try:
            proposal = proposal_from_tool_call(self._language_model.choose_tool(text, language))
        except (ValidationError, ValueError, TypeError):
            proposal = None

        if proposal is None:
            return ConversationResult(reply=messages.NOT_UNDERSTOOD, proposal=None)
        if proposal.kind == "appointment":
            return ConversationResult(reply=messages.APPOINTMENT_REQUEST_RECEIVED, proposal=proposal)
        return ConversationResult(reply=messages.MEDICATION_REQUEST_RECEIVED, proposal=proposal)
