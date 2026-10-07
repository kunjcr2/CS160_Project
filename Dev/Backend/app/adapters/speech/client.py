"""OpenAI speech adapters and deterministic fakes for local development."""

from io import BytesIO
from typing import Protocol

from openai import OpenAI


class SpeechToText(Protocol):
    def transcribe(self, audio: bytes, filename: str, content_type: str | None = None) -> str: ...


class TextToSpeech(Protocol):
    def synthesize(self, text: str, voice: str | None = None) -> bytes: ...


class FakeSpeechToText:
    def transcribe(self, audio: bytes, filename: str, content_type: str | None = None) -> str:
        if not audio:
            raise ValueError("Audio file is empty")
        return "This is a fake transcription."


class FakeTextToSpeech:
    def synthesize(self, text: str, voice: str | None = None) -> bytes:
        if not text.strip():
            raise ValueError("Text is empty")
        return b"FAKE_AUDIO"


class OpenAISpeechToText:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def transcribe(self, audio: bytes, filename: str, content_type: str | None = None) -> str:
        if not audio:
            raise ValueError("Audio file is empty")
        file_object = BytesIO(audio)
        file_object.name = filename
        result = self._client.audio.transcriptions.create(
            file=file_object,
            model=self._model,
            response_format="json",
        )
        return result.text


class OpenAITextToSpeech:
    def __init__(self, api_key: str, model: str, default_voice: str) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._default_voice = default_voice

    def synthesize(self, text: str, voice: str | None = None) -> bytes:
        if not text.strip():
            raise ValueError("Text is empty")
        response = self._client.audio.speech.create(
            model=self._model,
            voice=voice or self._default_voice,
            input=text,
            response_format="mp3",
        )
        return response.content


def build_speech_services(
    *,
    fake_ai: bool,
    api_key: str | None,
    stt_model: str,
    tts_model: str,
    tts_voice: str,
) -> tuple[SpeechToText, TextToSpeech]:
    if fake_ai:
        return FakeSpeechToText(), FakeTextToSpeech()
    if not api_key:
        raise ValueError("OPENAI_API_KEY must be set when FAKE_AI is false")
    return (
        OpenAISpeechToText(api_key, stt_model),
        OpenAITextToSpeech(api_key, tts_model, tts_voice),
    )
