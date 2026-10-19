import json

from pipeline.llm.mock_provider import MockProvider


def test_mock_provider_returns_valid_json_with_questions():
    provider = MockProvider()
    raw = provider.generate("cualquier prompt")
    data = json.loads(raw)
    assert "questions" in data
    assert len(data["questions"]) > 0
    for question in data["questions"]:
        assert "text" in question
        assert "[MOCK]" in question["text"]
