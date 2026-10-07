"""Text conversation endpoint (SR-08)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from openai import OpenAIError
from pydantic import BaseModel, Field

from app.adapters.llm.client import LanguageModel, build_language_model
from app.config import settings
from app.controllers.conversation.orchestrator import ConversationOrchestrator
from app.controllers.conversation.tools import Proposal
from app.views import messages

router = APIRouter(prefix="/ai", tags=["conversation"])


class ProcessRequest(BaseModel):
    text: Annotated[str, Field(min_length=1, max_length=2_000)]
    language: Annotated[str, Field(min_length=2, max_length=10)] = "en"


class ProcessResponse(BaseModel):
    reply: str
    proposal: Proposal | None = None


def get_language_model() -> LanguageModel:
    try:
        return build_language_model(
            fake_ai=settings.fake_ai,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
    except ValueError as error:
        raise HTTPException(status_code=503, detail=messages.AI_UNAVAILABLE) from error


@router.post("/process", response_model=ProcessResponse)
def process_text(request: ProcessRequest, language_model: LanguageModel = Depends(get_language_model)) -> ProcessResponse:
    """Interpret text into a proposal. This endpoint never creates or confirms an action."""
    try:
        result = ConversationOrchestrator(language_model).process(request.text, request.language)
    except OpenAIError as error:
        raise HTTPException(status_code=503, detail=messages.AI_UNAVAILABLE) from error
    return ProcessResponse(reply=result.reply, proposal=result.proposal)
