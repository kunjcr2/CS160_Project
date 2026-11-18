import pytest
from fastapi.testclient import TestClient

from app.adapters.llm.client import ModelResponse
from app.controllers.conversation.endpoints import get_language_model
from app.main import app
from app.model.guardrail import check_emergency
from app.views import messages


@pytest.mark.parametrize(
    "text",
    [
        "I have chest pain",
        "I can't breathe",
        "I fell in the bathroom",
        "I think it's a stroke",
        "I'm having a heart attack",
        "there is heavy bleeding from my arm",
        "I'm thinking about suicide",
    ],
)
def test_matches_emergency_phrases(text: str) -> None:
    assert check_emergency(text) == messages.EMERGENCY_DETECTED


def test_no_match_on_an_ordinary_message() -> None:
    assert check_emergency("Can you book me with Dr. Chen next Tuesday?") is None


@pytest.mark.parametrize(
    "text",
    [
        "I can't breathe",
        "I cant breathe",
        "I cannot breathe",
        "I can not breathe",
        "I CANT BREATHE",
        "I Cannot Breathe",
    ],
)
def test_matches_cant_breathe_spelling_variants(text: str) -> None:
    assert check_emergency(text) == messages.EMERGENCY_DETECTED


@pytest.mark.parametrize(
    "text",
    [
        "I HAVE CHEST PAIN",
        "I Can't Breathe",
        "HAVING A STROKE",
    ],
)
def test_matches_are_case_insensitive(text: str) -> None:
    assert check_emergency(text) == messages.EMERGENCY_DETECTED


def test_matches_a_phrase_with_extra_spaces() -> None:
    assert check_emergency("I   have    chest     pain") == messages.EMERGENCY_DETECTED


def test_matches_a_phrase_inside_a_normal_sentence() -> None:
    text = "Hi, I'm feeling dizzy and I have chest pain, what should I do?"
    assert check_emergency(text) == messages.EMERGENCY_DETECTED


@pytest.mark.parametrize(
    "text",
    [
        "My coworker is a good fellow.",
        "Strokes of genius, that painting is a chest of drawers.",
        "Tell me about my medication schedule.",
    ],
)
def test_does_not_false_match_inside_other_words(text: str) -> None:
    assert check_emergency(text) is None


def test_matches_a_fall_mentioned_about_someone_else() -> None:
    assert check_emergency("Mom fell down the stairs") == messages.EMERGENCY_DETECTED


@pytest.mark.parametrize(
    "text",
    [
        "I have chest pains",
        "chest pains",
        "I can't breath",
        "I cant breath",
        "I am having trouble breathing",
        "it's hard to breathe",
    ],
)
def test_matches_breathing_plurals_and_misspellings(text: str) -> None:
    assert check_emergency(text) == messages.EMERGENCY_DETECTED


@pytest.mark.parametrize(
    "text",
    [
        "I fell down",
        "I had a fall",
        "I think I'm having a stroke",
        "I think it's a stroke",
        "it won't stop bleeding",
        "it's bleeding a lot",
        "I'm bleeding badly",
    ],
)
def test_matches_narrowed_fall_stroke_and_bleeding_phrases(text: str) -> None:
    assert check_emergency(text) == messages.EMERGENCY_DETECTED


@pytest.mark.parametrize(
    "text",
    [
        "I fell asleep",
        "I fell asleep watching TV",
        "Book a follow-up with my stroke doctor",
        "my stroke doctor",
        "My gums are bleeding a little when I brush",
        "my gums are bleeding a little",
    ],
)
def test_does_not_over_trigger_on_narrowed_phrases(text: str) -> None:
    assert check_emergency(text) is None


class ExplodingLanguageModel:
    """Fails the test if the AI is ever called."""

    def respond(self, text: str, language: str) -> ModelResponse:
        raise AssertionError("the language model must not be called for an emergency message")


def test_process_endpoint_returns_the_emergency_message_without_calling_the_ai() -> None:
    app.dependency_overrides[get_language_model] = lambda: ExplodingLanguageModel()
    try:
        response = TestClient(app).post(
            "/api/v1/ai/process", json={"text": "I fell and I can't get up, chest pain too"}
        )
    finally:
        app.dependency_overrides.pop(get_language_model, None)

    assert response.status_code == 200
    assert response.json() == {"reply": messages.EMERGENCY_DETECTED, "proposal": None}
