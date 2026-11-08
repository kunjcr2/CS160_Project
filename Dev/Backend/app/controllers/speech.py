"""Standalone speech-to-text and text-to-speech endpoints."""

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from openai import OpenAIError
from pydantic import BaseModel, Field

from app.adapters.speech import SpeechToText, TextToSpeech, build_speech_services
from app.config import settings

router = APIRouter(prefix="/ai", tags=["speech"])
MAX_AUDIO_BYTES = 10 * 1024 * 1024
SUPPORTED_AUDIO_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/webm",
    "audio/mp4",
    "audio/x-m4a",
    "audio/m4a",
    "video/webm",
    "video/mp4",
}


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2_000)
    voice: str | None = Field(default=None, min_length=1, max_length=40)


class TranscriptionResponse(BaseModel):
    text: str


def get_speech_services() -> tuple[SpeechToText, TextToSpeech]:
    try:
        return build_speech_services(
            fake_ai=settings.fake_ai,
            api_key=settings.openai_api_key,
            stt_model=settings.openai_stt_model,
            tts_model=settings.openai_tts_model,
            tts_voice=settings.openai_tts_voice,
        )
    except ValueError as error:
        raise HTTPException(status_code=503, detail="Speech service is unavailable") from error


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    audio: Annotated[UploadFile, File()],
) -> TranscriptionResponse:
    if audio.content_type not in SUPPORTED_AUDIO_TYPES:
        raise HTTPException(status_code=415, detail="Unsupported audio format")
    speech_to_text, _ = get_speech_services()
    try:
        contents = await audio.read(MAX_AUDIO_BYTES + 1)
        if len(contents) > MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="Audio file is too large")
        text = await run_in_threadpool(
            speech_to_text.transcribe,
            contents,
            audio.filename or "audio.webm",
            audio.content_type,
        )
    except (OpenAIError, ValueError) as error:
        raise HTTPException(status_code=503, detail="Speech transcription failed") from error
    return TranscriptionResponse(text=text)


@router.post("/tts")
def synthesize_speech(request: TTSRequest) -> Response:
    _, text_to_speech = get_speech_services()
    try:
        audio = text_to_speech.synthesize(request.text, request.voice)
    except (OpenAIError, ValueError) as error:
        raise HTTPException(status_code=503, detail="Speech synthesis failed") from error
    return Response(content=audio, media_type="audio/mpeg")
