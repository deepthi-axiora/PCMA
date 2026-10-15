import pytest

from app.core.config import settings
from app.services.llm_provider import (
    LLMProviderError,
    MockLLMProvider,
    OpenAILLMProvider,
    get_llm_provider,
)


@pytest.mark.asyncio
async def test_mock_llm_provider():
    provider = MockLLMProvider()
    segments = [{"id": 1, "text": "We decided on project architecture by Friday?", "speaker_label": "Alice"}]
    facts, prompt_tokens, comp_tokens, cost = await provider.extract_structured_facts(segments)
    assert len(facts["decisions"]) >= 1
    assert prompt_tokens > 0

    answer = await provider.generate_answer(
        "User Question: What did we decide?\n<user_retrieved_data>\n- We decided on PostgreSQL.\n</user_retrieved_data>"
    )
    assert "PostgreSQL" in answer


@pytest.mark.asyncio
async def test_openai_llm_provider_construction(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "llm_api_key", "sk-fake-test-key-12345")
    monkeypatch.setattr(settings, "stt_api_key", "sk-stt-key-different")

    provider = get_llm_provider()
    assert isinstance(provider, OpenAILLMProvider)
    assert provider.api_key == "sk-fake-test-key-12345"


@pytest.mark.asyncio
async def test_llm_provider_missing_credentials_raises_error(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "llm_api_key", None)
    monkeypatch.setattr(settings, "stt_api_key", "sk-stt-key-should-not-be-used")

    with pytest.raises(LLMProviderError) as exc_info:
        get_llm_provider()

    assert "LLM_API_KEY is not configured" in str(exc_info.value)
    # Verify STT credentials were not leaked or used
    assert "sk-stt-key" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_invalid_llm_provider_raises_error(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "invalid_provider_name")

    with pytest.raises(LLMProviderError) as exc_info:
        get_llm_provider()

    assert "Invalid LLM provider" in str(exc_info.value)


@pytest.mark.asyncio
async def test_mock_llm_compound_statement_and_action_item_extraction():
    provider = MockLLMProvider()
    segments = [
        {
            "id": 21,
            "text": "We decided to adopt the new architecture, allies will do the deployment by Friday.",
            "speaker_label": "Speaker 1",
        }
    ]
    facts, _, _, _ = await provider.extract_structured_facts(segments)
    # Decision extracted separately
    assert len(facts["decisions"]) == 1
    assert facts["decisions"][0]["text"] == "We decided to adopt the new architecture"
    # Action item extracted separately, preserving verbatim transcript text
    assert len(facts["action_items"]) == 1
    assert facts["action_items"][0]["text"] == "allies will do the deployment by Friday"
    assert facts["action_items"][0]["assignee_name"] == "allies"
    # Deadline extracted from action item
    assert len(facts["deadlines"]) == 1
    assert facts["deadlines"][0]["raw_deadline_text"] == "by friday"
    assert facts["deadlines"][0]["title"] == "Deployment by Friday"


@pytest.mark.asyncio
async def test_mock_llm_excludes_test_instruction_meta_decisions():
    provider = MockLLMProvider()
    segments = [
        {
            "id": 23,
            "text": "The current mock extraction rules should recognize examples of decisions, tasks, commitment",
            "speaker_label": "Speaker 1",
        }
    ]
    facts, _, _, _ = await provider.extract_structured_facts(segments)
    assert len(facts["decisions"]) == 0
    assert len(facts["action_items"]) == 0
    assert len(facts["commitments"]) == 0


@pytest.mark.asyncio
async def test_mock_llm_conversation_6_full_simulation():
    provider = MockLLMProvider()
    segments = [
        {"id": 21, "text": "We decided to adopt the new architecture, allies will do the deployment by Friday."},
        {"id": 22, "text": "I promise to deliver the report, can we test on a physical device."},
        {"id": 23, "text": "The current mock extraction rules should recognize examples of decisions, tasks, commitment"},
        {"id": 24, "text": "deadlines and questions."},
    ]
    facts, _, _, _ = await provider.extract_structured_facts(segments)
    assert len(facts["decisions"]) == 1
    assert facts["decisions"][0]["text"] == "We decided to adopt the new architecture"
    assert len(facts["action_items"]) == 1
    assert facts["action_items"][0]["text"] == "allies will do the deployment by Friday"
    assert len(facts["commitments"]) == 1
    assert facts["commitments"][0]["text"] == "I promise to deliver the report"
    assert len(facts["deadlines"]) == 1
    assert facts["deadlines"][0]["raw_deadline_text"] == "by friday"
    assert len(facts["questions"]) == 1
    assert facts["questions"][0]["question_text"] == "Can we test on a physical device?"

