import json
from types import SimpleNamespace
from unittest.mock import Mock

from app.adapters.llm.client import OpenAILanguageModel


def test_openai_language_model_requests_and_parses_structured_json():
    language_model = OpenAILanguageModel("test-key", "gpt-6-luna", "none", 120)
    language_model._client = Mock()
    language_model._client.responses.create.return_value = SimpleNamespace(
        output_text=json.dumps(
            {
                "reply": "What date would you prefer for your appointment with Dr. Chen?",
                "proposal": {"kind": "appointment", "doctor": "Dr. Chen", "date_hint": None},
            }
        )
    )

    result = language_model.respond("I need an appointment with Dr. Chen.", "en")

    assert result.reply == "What date would you prefer for your appointment with Dr. Chen?"
    assert result.proposal == {"kind": "appointment", "doctor": "Dr. Chen", "date_hint": None}
    request = language_model._client.responses.create.call_args.kwargs
    assert "tools" not in request
    assert request["reasoning"] == {"effort": "none"}
    assert request["max_output_tokens"] == 120
    assert request["text"]["format"]["type"] == "json_schema"
    assert request["text"]["format"]["strict"] is True
