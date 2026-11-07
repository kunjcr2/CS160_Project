from fastapi.testclient import TestClient

from app.adapters.llm.client import ModelResponse
from app.controllers.conversation.endpoints import get_language_model
from app.main import app


class StaticLanguageModel:
    """Test double for the dependency; production always uses OpenAI."""

    def __init__(self, response: ModelResponse) -> None:
        self._response = response

    def respond(self, text: str, language: str) -> ModelResponse:
        return self._response


def post_with_model_response(payload: dict[str, str], response: ModelResponse):
    app.dependency_overrides[get_language_model] = lambda: StaticLanguageModel(response)
    try:
        return TestClient(app).post("/api/v1/ai/process", json=payload)
    finally:
        app.dependency_overrides.pop(get_language_model, None)


def test_appointment_request_returns_a_typed_proposal():
    response = post_with_model_response(
        {"text": "Please book me with Dr. Chen next Tuesday."},
        ModelResponse(
            reply="I can look for appointments with Dr. Chen next Tuesday.",
            proposal={"kind": "appointment", "doctor": "Dr. Chen", "date_hint": "next Tuesday"},
        ),
    )

    assert response.status_code == 200
    assert response.json()["proposal"] == {
        "kind": "appointment",
        "doctor": "Dr. Chen",
        "date_hint": "next Tuesday",
    }
    assert response.json()["reply"] == "I can look for appointments with Dr. Chen next Tuesday."


def test_appointment_request_without_a_doctor_asks_for_one():
    response = post_with_model_response(
        {"text": "Schedule a doctor visit tomorrow."},
        ModelResponse(
            reply="Which doctor would you like to see?",
            proposal={"kind": "appointment", "doctor": None, "date_hint": "tomorrow"},
        ),
    )

    assert response.status_code == 200
    assert response.json()["reply"] == "Which doctor would you like to see?"


def test_appointment_request_without_a_date_asks_for_a_date():
    response = post_with_model_response(
        {"text": "I need an appointment with Dr. Chen."},
        ModelResponse(
            reply="What date would you prefer for your appointment with Dr. Chen?",
            proposal={"kind": "appointment", "doctor": "Dr. Chen", "date_hint": None},
        ),
    )

    assert response.status_code == 200
    assert response.json() == {
        "reply": "What date would you prefer for your appointment with Dr. Chen?",
        "proposal": {"kind": "appointment", "doctor": "Dr. Chen", "date_hint": None},
    }


def test_medication_request_returns_a_typed_proposal_without_creating_a_reminder():
    response = post_with_model_response(
        {"text": "Remind me to take my aspirin at 8 pm."},
        ModelResponse(
            reply="I can set a reminder for aspirin at 8 pm.",
            proposal={"kind": "medication_reminder", "medication": "aspirin", "time_hint": "8 pm"},
        ),
    )

    assert response.status_code == 200
    assert response.json()["proposal"] == {
        "kind": "medication_reminder",
        "medication": "aspirin",
        "time_hint": "8 pm",
    }
    assert response.json()["reply"] == "I can set a reminder for aspirin at 8 pm."


def test_unknown_request_does_not_propose_an_action():
    response = post_with_model_response(
        {"text": "Tell me a joke."},
        ModelResponse(reply="Sorry, I didn't understand. Could you say that another way?", proposal=None),
    )

    assert response.status_code == 200
    assert response.json()["proposal"] is None
