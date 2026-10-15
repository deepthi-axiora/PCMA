from dataclasses import dataclass
import pytest
from app.core.config import settings
from app.services.stt_provider import (
    LocalFasterWhisperProvider,
    OpenAIWhisperProvider,
    STTError,
    create_stt_provider,
)


@dataclass
class FakeSegment:
    start: float
    end: float
    text: str
    avg_logprob: float = -0.2


@dataclass
class FakeInfo:
    language: str = "en"
    language_probability: float = 0.98


class FakeWhisperModel:
    def __init__(self, model_size_or_path, device="cpu", compute_type="int8"):
        self.model_size_or_path = model_size_or_path
        self.device = device
        self.compute_type = compute_type

    def transcribe(self, audio_path, beam_size=5, temperature=0.0):
        segments = [
            FakeSegment(0.0, 1.5, " Hello world", -0.1),
            FakeSegment(1.5, 3.0, " Local STT test", -0.2),
        ]
        return iter(segments), FakeInfo()


def test_create_stt_provider_factory(monkeypatch):
    monkeypatch.setattr(settings, "stt_provider", "local")
    provider = create_stt_provider()
    assert isinstance(provider, LocalFasterWhisperProvider)
    assert provider.name == "local"
    assert provider.model == settings.local_stt_model

    monkeypatch.setattr(settings, "stt_provider", "openai_whisper")
    monkeypatch.setattr(settings, "stt_api_key", "test-key")
    openai_provider = create_stt_provider()
    assert isinstance(openai_provider, OpenAIWhisperProvider)
    assert openai_provider.name == "openai_whisper"

    with pytest.raises(STTError) as exc_info:
        create_stt_provider("unknown_provider")
    assert exc_info.value.code == "stt_provider_not_supported"


@pytest.mark.asyncio
async def test_local_faster_whisper_provider_transcribe_mocked(monkeypatch):
    provider = LocalFasterWhisperProvider(model="small", device="cpu", compute_type="int8")
    monkeypatch.setattr(provider, "_get_model", lambda: FakeWhisperModel("small"))

    audio_bytes = b"fake wav audio header and data"
    transcript = await provider.transcribe(audio_bytes, "audio/wav")

    assert transcript.language == "en"
    assert transcript.model == "small"
    assert len(transcript.segments) == 2
    assert transcript.segments[0].text == "Hello world"
    assert transcript.segments[0].start_seconds == 0.0
    assert transcript.segments[0].end_seconds == 1.5
    assert 0.0 <= transcript.segments[0].confidence <= 1.0
    assert transcript.segments[1].text == "Local STT test"


@pytest.mark.asyncio
async def test_local_faster_whisper_provider_empty_audio():
    provider = LocalFasterWhisperProvider(model="small", device="cpu", compute_type="int8")
    with pytest.raises(STTError) as exc_info:
        await provider.transcribe(b"", "audio/wav")
    assert exc_info.value.code == "empty_audio"
