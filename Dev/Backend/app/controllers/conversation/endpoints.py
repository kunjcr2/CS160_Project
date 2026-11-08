"""Text and voice conversation endpoints (SR-08)."""

import base64
from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from openai import OpenAIError
from pydantic import BaseModel, Field

from app.adapters.llm.client import LanguageModel, build_language_model
from app.config import settings
from app.controllers.conversation.orchestrator import ConversationOrchestrator
from app.controllers.conversation.tools import Proposal
from app.controllers.speech import MAX_AUDIO_BYTES, SUPPORTED_AUDIO_TYPES, get_speech_services
from app.views import messages

router = APIRouter(prefix="/ai", tags=["conversation"])


class ProcessRequest(BaseModel):
    text: Annotated[str, Field(min_length=1, max_length=2_000)]
    language: Annotated[str, Field(min_length=2, max_length=10)] = "en"
    unclear_turns: Annotated[int, Field(ge=0, le=3)] = 0


class ProcessResponse(BaseModel):
    reply: str
    proposal: Proposal | None = None
    readback: str | None = None
    language: str = "en"
    unclear_turns: int = 0
    offer_human_help: bool = False


class VoiceResponse(ProcessResponse):
    transcript: str
    audio_base64: str | None = None
    transcription_ms: int


def get_language_model() -> LanguageModel:
    try:
        return build_language_model(
            fake_ai=settings.fake_ai,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            reasoning_effort=settings.openai_reasoning_effort,
            max_output_tokens=settings.openai_max_output_tokens,
        )
    except ValueError as error:
        raise HTTPException(status_code=503, detail=messages.AI_UNAVAILABLE) from error


@router.post("/process", response_model=ProcessResponse)
def process_text(
    request: ProcessRequest, language_model: Annotated[LanguageModel, Depends(get_language_model)]
) -> ProcessResponse:
    """Interpret text into a proposal. This endpoint never creates or confirms an action."""
    try:
        result = ConversationOrchestrator(language_model).process(
            request.text, request.language, request.unclear_turns
        )
    except OpenAIError as error:
        raise HTTPException(status_code=503, detail=messages.AI_UNAVAILABLE) from error
    return ProcessResponse(**result.__dict__)


@router.post("/voice", response_model=VoiceResponse)
async def process_voice(
    audio: Annotated[UploadFile, File()],
    language_model: Annotated[LanguageModel, Depends(get_language_model)],
    language: Annotated[str, Form()] = "en",
    unclear_turns: Annotated[int, Form(ge=0, le=3)] = 0,
) -> VoiceResponse:
    """Transcribe, interpret, and speak the response; never execute the proposal."""
    if audio.content_type not in SUPPORTED_AUDIO_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported audio format")
    contents = await audio.read(MAX_AUDIO_BYTES + 1)
    if len(contents) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio file is too large")
    if not contents:
        raise HTTPException(status_code=422, detail="Audio file is empty")
    speech_to_text, text_to_speech = get_speech_services()
    normalized_language = language.split("-")[0].lower()
    if normalized_language not in ("en", "es"):
        normalized_language = "en"
    started = perf_counter()
    try:
        transcript = await run_in_threadpool(
            speech_to_text.transcribe,
            contents,
            audio.filename or "audio.webm",
            audio.content_type,
            normalized_language,
        )
    except (OpenAIError, ValueError) as error:
        raise HTTPException(status_code=503, detail="Speech transcription failed") from error
    elapsed_ms = round((perf_counter() - started) * 1000)
    try:
        result = await run_in_threadpool(
            ConversationOrchestrator(language_model).process,
            transcript,
            normalized_language,
            unclear_turns,
        )
    except OpenAIError as error:
        raise HTTPException(status_code=503, detail=messages.AI_UNAVAILABLE) from error
    spoken = f"{result.reply} {result.readback}" if result.readback else result.reply
    try:
        audio_bytes = await run_in_threadpool(text_to_speech.synthesize, spoken)
        audio_base64 = base64.b64encode(audio_bytes).decode("ascii")
    except (OpenAIError, ValueError):
        audio_base64 = None  # The text response remains usable when speech fails.
    return VoiceResponse(
        **result.__dict__,
        transcript=transcript,
        audio_base64=audio_base64,
        transcription_ms=elapsed_ms,
    )
