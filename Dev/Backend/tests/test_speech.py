from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.adapters.speech.client import OpenAISpeechToText, OpenAITextToSpeech
from app.controllers.conversation import endpoints
from app.main import app


class StaticSpeechToText:
    def transcribe(self, audio, filename, content_type=None, language=None):
        assert audio == b"audio bytes"
        assert language == "es"
        return "Quiero una cita con Dra. Ruiz mañana"


class RecordingTextToSpeech:
    def __init__(self):
        self.spoken = None

    def synthesize(self, text, voice=None):
        self.spoken = text
        return b"mp3 bytes"


def test_fake_transcription_accepts_uploaded_audio():
    response = TestClient(app).post(
        "/api/v1/ai/transcribe",
        files={"audio": ("request.webm", b"audio bytes", "audio/webm")},
    )

    assert response.status_code == 200
    assert response.json() == {"text": "This is a fake transcription."}


def test_fake_tts_returns_audio_bytes():
    response = TestClient(app).post("/api/v1/ai/tts", json={"text": "Hello there."})

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == b"FAKE_AUDIO"


def test_transcription_rejects_empty_upload():
    response = TestClient(app).post(
        "/api/v1/ai/transcribe",
        files={"audio": ("request.webm", b"", "audio/webm")},
    )

    assert response.status_code == 503


def test_voice_pipeline_transcribes_and_speaks_readback(monkeypatch):
    speaker = RecordingTextToSpeech()
    monkeypatch.setattr(endpoints, "get_speech_services", lambda: (StaticSpeechToText(), speaker))
    response = TestClient(app).post(
        "/api/v1/ai/voice",
        data={"language": "es"},
        files={"audio": ("request.webm", b"audio bytes", "audio/webm")},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["transcript"] == "Quiero una cita con Dra. Ruiz mañana"
    assert result["proposal"]["kind"] == "appointment"
    assert result["audio_base64"] == "bXAzIGJ5dGVz"
    assert result["transcription_ms"] >= 0
    assert result["readback"] in speaker.spoken


def test_voice_rejects_unsupported_audio():
    response = TestClient(app).post(
        "/api/v1/ai/voice",
        files={"audio": ("request.txt", b"audio bytes", "text/plain")},
    )
    assert response.status_code == 415


def test_openai_transcription_sends_audio_and_spanish_hint():
    recognizer = OpenAISpeechToText("test-key", "gpt-4o-mini-transcribe")
    recognizer._client = Mock()
    recognizer._client.audio.transcriptions.create.return_value = SimpleNamespace(text="  hola  ")
    assert recognizer.transcribe(b"audio bytes", "clip.webm", "audio/webm", "es") == "hola"
    request = recognizer._client.audio.transcriptions.create.call_args.kwargs
    assert request["language"] == "es"
    assert request["file"].name == "clip.webm"
    assert request["file"].getvalue() == b"audio bytes"


def test_openai_tts_uses_configured_voice_and_mp3():
    speaker = OpenAITextToSpeech("test-key", "gpt-4o-mini-tts", "alloy")
    speaker._client = Mock()
    speaker._client.audio.speech.create.return_value = SimpleNamespace(content=b"mp3")
    assert speaker.synthesize("Please confirm", "nova") == b"mp3"
    request = speaker._client.audio.speech.create.call_args.kwargs
    assert request["voice"] == "nova"
    assert request["response_format"] == "mp3"
