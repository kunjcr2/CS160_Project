from fastapi.testclient import TestClient

from app.main import app


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
