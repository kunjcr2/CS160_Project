"""Speech-to-text and text-to-speech adapters."""

from app.adapters.speech.client import (
    SpeechToText,
    TextToSpeech,
    build_speech_services,
)

__all__ = ["SpeechToText", "TextToSpeech", "build_speech_services"]
