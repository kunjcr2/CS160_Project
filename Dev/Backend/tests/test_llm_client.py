import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.adapters.llm.client import OpenAILanguageModel


@pytest.mark.parametrize(
    ("tool", "arguments", "kind"),
    [
        ("propose_appointment", {"doctor": "Dr. Chen", "date_hint": "Tuesday"}, "appointment"),
        (
            "propose_medication_reminder",
            {"medication": "aspirin", "time_hint": "8 pm"},
            "medication_reminder",
        ),
        ("propose_refill", {"medication": "lisinopril"}, "refill"),
        ("propose_human_help", {"summary": None}, "human_help"),
    ],
)
def test_openai_function_calls_become_typed_proposals(tool, arguments, kind):
    model = OpenAILanguageModel("test-key", "gpt-6-luna", "none", 300)
    model._client = Mock()
    model._client.responses.create.return_value = SimpleNamespace(
        output=[SimpleNamespace(type="function_call", name=tool, arguments=json.dumps(arguments))],
        output_text="",
    )

    result = model.respond("Please help", "en")

    assert result.proposal == {"kind": kind, **arguments}
    request = model._client.responses.create.call_args.kwargs
    assert request["tools"]
    assert request["parallel_tool_calls"] is False
    assert request["store"] is False
    assert request["max_output_tokens"] == 300


def test_unknown_tool_is_rejected():
    model = OpenAILanguageModel("test-key", "gpt-6-luna", "none", 300)
    model._client = Mock()
    model._client.responses.create.return_value = SimpleNamespace(
        output=[SimpleNamespace(type="function_call", name="book_now", arguments="{}")],
        output_text="",
    )
    with pytest.raises(ValueError, match="unknown tool"):
        model.respond("Book it", "en")
