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


class ConversationOrchestrator:
    def __init__(self, language_model: LanguageModel) -> None:
        self._language_model = language_model

    def process(self, text: str, language: str) -> ConversationResult:
        try:
            model_response = self._language_model.respond(text, language)
            proposal = proposal_from_json(model_response.proposal)
        except (ValidationError, ValueError, TypeError):
            return ConversationResult(reply=messages.NOT_UNDERSTOOD, proposal=None)

        if proposal is None:
            return ConversationResult(reply=model_response.reply, proposal=None)
        return ConversationResult(reply=model_response.reply, proposal=proposal)
