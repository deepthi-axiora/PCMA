import io
import logging
import struct
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.database.session import AsyncSessionLocal
from app.models import (AIProcessingJob, AuditEvent, Conversation, Recording, Transcript,
                        TranscriptSegment, User, UserProfile)
from app.services.audio_preprocessing import create_speech_chunks, prepare_speech_chunks
from app.services.audio_storage import read_encrypted_audio, store_encrypted_audio
from app.services.recording_service import RecordingError, start_recording, stop_recording, upload_audio
from app.services.stt_provider import (
    OpenAIWhisperProvider,
    ProviderSegment,
    ProviderTranscript,
    STTError,
    create_stt_provider,
)
from app.services.transcription_service import (
    get_transcript,
    get_transcription_status,
    process_next_transcription_job,
    retry_transcription,
)


def wav_fixture(speech_seconds=2.0, silence_seconds=0.4, amplitude=5000):
    sample_rate = 16000
    speech_frames = int(speech_seconds * sample_rate)
    silence_frames = int(silence_seconds * sample_rate)
    samples = ([amplitude] * speech_frames + [0] * silence_frames +
               [amplitude] * speech_frames)
    data = struct.pack(f"<{len(samples)}h", *samples)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(data)
    return buffer.getvalue()


class SuccessfulProvider:
    name = "unit_test_provider"
    model = "deterministic-test-model"

    async def transcribe(self, audio: bytes, content_type: str):
        assert content_type == "audio/wav"
        with wave.open(io.BytesIO(audio), "rb") as source:
            duration = source.getnframes() / source.getframerate()
        return ProviderTranscript(
            language="english",
            model=self.model,
            segments=[ProviderSegment(0.1, min(0.7, duration), "fixture transcript", 0.25)],
        )


class FailingProvider:
    name = "unit_test_provider"
    model = "deterministic-test-model"

    def __init__(self, retryable=True):
        self.retryable = retryable

    async def transcribe(self, audio: bytes, content_type: str):
        raise STTError("provider_fixture_failure", "fixture provider failure",
                       retryable=self.retryable)


class PartialFailureProvider:
    name = "unit_test_provider"
    model = "deterministic-test-model"

    def __init__(self):
        self.calls = 0

    async def transcribe(self, audio: bytes, content_type: str):
        self.calls += 1
        if self.calls > 1:
            raise STTError("later_chunk_failed", "fixture failure after a saved chunk",
                           retryable=False)
        return ProviderTranscript("english", [ProviderSegment(0.1, 0.7, "saved portion", 0.8)], self.model)


async def create_stopped_recording(db, tmp_path: Path, monkeypatch):
    user = User(auth_id=f"stt-test-{uuid4()}")
    db.add(user)
    await db.flush()
    db.add(UserProfile(user_id=user.id, jurisdiction="IN"))
    await db.commit()
    recording = await start_recording(
        db, user.id, audio_source="phone_microphone", source_available=True,
        microphone_permission_granted=True, consent_acknowledged=True,
    )
    audio = await upload_audio(db, recording.id, user.id, wav_fixture(), "audio/wav", None)
    await stop_recording(db, recording.id, user.id)
    return user.id, recording.id, audio


@pytest.mark.asyncio
async def test_vad_merges_brief_silence_and_splits_long_speech(monkeypatch):
    monkeypatch.setattr(settings, "stt_vad_silence_ms", 500)
    monkeypatch.setattr(settings, "stt_vad_padding_ms", 0)
    monkeypatch.setattr(settings, "stt_max_chunk_duration_seconds", 1)
    chunks, duration_ms = create_speech_chunks(wav_fixture(0.8, 0.2))
    assert duration_ms == 1800
    assert len(chunks) == 2
    assert [chunk.index for chunk in chunks] == [0, 1]
    assert chunks[0].start_ms == 0
    assert chunks[-1].end_ms <= duration_ms


@pytest.mark.asyncio
async def test_vad_rejects_silence_and_too_short_audio(monkeypatch):
    monkeypatch.setattr(settings, "stt_min_audio_duration_ms", 1000)
    with pytest.raises(STTError) as silence_error:
        create_speech_chunks(wav_fixture(0.8, 1.0, amplitude=0))
    assert silence_error.value.code == "no_speech_detected"
    with pytest.raises(STTError) as duration_error:
        create_speech_chunks(wav_fixture(0.2, 0, amplitude=5000))
    assert duration_error.value.code == "audio_too_short"


@pytest.mark.asyncio
async def test_mp3_storage_retrieval_and_ffmpeg_preprocessing_preserve_18_second_audio(
    monkeypatch, tmp_path: Path, caplog,
):
    monkeypatch.setattr(settings, "audio_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "audio_encryption_key",
                        "a2tra2tra2tra2tra2tra2tra2tra2tra2tra2tra2s=")

    # Matches the uploaded 585,978-byte MP3 size; FFmpeg is isolated behind a
    # deterministic stdout double because the binary is an external dependency.
    mp3_bytes = b"ID3" + bytes(585975)
    caplog.set_level(logging.INFO, logger="pcma.audio_preprocessing")
    storage_ref = store_encrypted_audio(mp3_bytes)
    encrypted_path = tmp_path / storage_ref
    assert encrypted_path.stat().st_size == len(mp3_bytes) + 28
    assert encrypted_path.read_bytes() != mp3_bytes

    retrieved_bytes = read_encrypted_audio(storage_ref)
    assert retrieved_bytes == mp3_bytes
    assert len(retrieved_bytes) == 585978

    # 292,989 mono samples at 16 kHz are approximately 18.3118 seconds.
    pcm_output = struct.pack("<h", 5000) * 292_989

    class FakeFFmpegProcess:
        returncode = 0

        async def communicate(self, supplied_audio):
            assert supplied_audio == mp3_bytes
            return pcm_output, None

    async def fake_ffmpeg(*args, **kwargs):
        assert args[-3:] == ("-f", "s16le", "pipe:1")
        assert kwargs["stdin"] is not None
        return FakeFFmpegProcess()

    monkeypatch.setattr("app.services.audio_preprocessing.asyncio.create_subprocess_exec", fake_ffmpeg)
    chunks, duration_ms = await prepare_speech_chunks(retrieved_bytes)

    assert duration_ms == 18311
    assert len(chunks) == 1
    assert chunks[0].start_ms == 0
    assert chunks[0].end_ms == 18311
    messages = [record.getMessage() for record in caplog.records]
    assert any("ffmpeg_completed return_code=0 raw_pcm_bytes=585978" in m for m in messages)
    assert any("audio_wav_built_in_memory" in m and "wav_data_bytes=585978" in m
               for m in messages)
    assert any("audio_vad_completed duration_ms=18311 chunks=1" in m for m in messages)
    assert all(settings.audio_encryption_key not in m for m in messages)
    with wave.open(io.BytesIO(chunks[0].audio), "rb") as converted:
        assert converted.getnchannels() == 1
        assert converted.getsampwidth() == 2
        assert converted.getframerate() == 16000
        assert converted.getnframes() == 292_989


@pytest.mark.asyncio
async def test_stop_queues_job_and_worker_persists_encrypted_owner_scoped_transcript(
    monkeypatch, tmp_path: Path,
):
    monkeypatch.setattr(settings, "audio_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "audio_encryption_key",
                        "a2tra2tra2tra2tra2tra2tra2tra2tra2tra2tra2s=")
    monkeypatch.setattr(settings, "stt_supported_languages", "english")
    async with AsyncSessionLocal() as db:
        user_id, recording_id, _audio = await create_stopped_recording(db, tmp_path, monkeypatch)
        job = (await db.execute(select(AIProcessingJob).where(
            AIProcessingJob.recording_id == recording_id,
            AIProcessingJob.stage == "transcription",
        ))).scalar_one()
        assert job.status == "queued"
        assert await process_next_transcription_job(db, SuccessfulProvider()) is True

        saved_job = (await db.execute(select(AIProcessingJob).where(
            AIProcessingJob.id == job.id
        ))).scalar_one()
        recording = (await db.execute(select(Recording).where(
            Recording.id == recording_id
        ))).scalar_one()
        transcript = (await db.execute(select(Transcript).where(
            Transcript.recording_id == recording_id
        ))).scalar_one()
        segment = (await db.execute(select(TranscriptSegment).where(
            TranscriptSegment.transcript_id == transcript.id
        ))).scalar_one()
        assert saved_job.status == "complete"
        conversation = (await db.execute(select(Conversation).where(
            Conversation.recording_id == recording_id
        ))).scalar_one()
        diarization_job = (await db.execute(select(AIProcessingJob).where(
            AIProcessingJob.recording_id == recording_id,
            AIProcessingJob.stage == "diarization",
        ))).scalar_one()
        assert conversation.user_id == user_id
        assert diarization_job.status == "queued"
        assert saved_job.model_used == "deterministic-test-model"
        assert recording.state == "ready_for_review"
        assert transcript.language == "english"
        assert transcript.detected_languages == '["english"]'
        assert segment.low_confidence is True
        assert segment.text_ciphertext != b"fixture transcript"

        output = await get_transcript(db, recording_id, user_id)
        assert output["segments"][0]["text"] == "fixture transcript"
        another_user = User(auth_id=f"other-stt-{uuid4()}")
        db.add(another_user)
        await db.commit()
        assert await get_transcript(db, recording_id, another_user.id) is None
        assert await get_transcription_status(db, recording_id, another_user.id) is None
        audit_types = (await db.execute(select(AuditEvent.event_type))).scalars().all()
        assert "transcription.queued" in audit_types
        assert "transcription.started" in audit_types
        assert "transcription.completed" in audit_types
        assert await process_next_transcription_job(db, SuccessfulProvider()) is False
        event_metadata = (await db.execute(select(AuditEvent.metadata_json))).scalars().all()
        assert all("fixture transcript" not in item for item in event_metadata)


@pytest.mark.asyncio
async def test_transient_provider_failure_retries_then_user_can_retry(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(settings, "audio_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "audio_encryption_key",
                        "a2tra2tra2tra2tra2tra2tra2tra2tra2tra2tra2s=")
    monkeypatch.setattr(settings, "stt_max_attempts", 2)
    monkeypatch.setattr(settings, "stt_retry_base_seconds", 1)
    monkeypatch.setattr(settings, "stt_supported_languages", "english")
    async with AsyncSessionLocal() as db:
        user_id, recording_id, _audio = await create_stopped_recording(db, tmp_path, monkeypatch)
        assert await process_next_transcription_job(db, FailingProvider()) is True
        job = await get_transcription_status(db, recording_id, user_id)
        assert job.status == "queued"
        assert job.attempts == 1
        retry_at = job.available_at
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        assert retry_at > datetime.now(timezone.utc)
        job.available_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db.commit()
        assert await process_next_transcription_job(db, FailingProvider()) is True
        job = await get_transcription_status(db, recording_id, user_id)
        recording = (await db.execute(select(Recording).where(
            Recording.id == recording_id
        ))).scalar_one()
        assert job.status == "failed"
        assert job.attempts == 2
        assert job.last_error_code == "provider_fixture_failure"
        assert recording.state == "failed"

        retry = await retry_transcription(db, recording_id, user_id)
        assert retry.status == "queued"
        await db.refresh(recording)
        assert recording.state == "processing"
        assert await process_next_transcription_job(db, SuccessfulProvider()) is True
        recording = (await db.execute(select(Recording).where(
            Recording.id == recording_id
        ))).scalar_one()
        assert recording.state == "ready_for_review"


@pytest.mark.asyncio
async def test_missing_provider_credentials_fail_job_without_network_call(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(settings, "audio_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "audio_encryption_key",
                        "a2tra2tra2tra2tra2tra2tra2tra2tra2tra2tra2s=")
    monkeypatch.setattr(settings, "stt_provider", "openai_whisper")
    monkeypatch.setattr(settings, "stt_api_key", None)
    async with AsyncSessionLocal() as db:
        user_id, recording_id, _audio = await create_stopped_recording(db, tmp_path, monkeypatch)
        assert await process_next_transcription_job(db) is True
        job = await get_transcription_status(db, recording_id, user_id)
        recording = (await db.execute(select(Recording).where(
            Recording.id == recording_id
        ))).scalar_one()
        assert job.status == "failed"
        assert job.last_error_code == "stt_provider_not_configured"
        assert recording.state == "failed"


@pytest.mark.asyncio
async def test_unsupported_language_is_permanent_and_retry_is_owner_scoped(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(settings, "audio_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "audio_encryption_key",
                        "a2tra2tra2tra2tra2tra2tra2tra2tra2tra2tra2s=")
    monkeypatch.setattr(settings, "stt_supported_languages", "en")
    async with AsyncSessionLocal() as db:
        user_id, recording_id, _audio = await create_stopped_recording(db, tmp_path, monkeypatch)
        assert await process_next_transcription_job(db, SuccessfulProvider()) is True
        job = await get_transcription_status(db, recording_id, user_id)
        assert job.status == "failed"
        assert job.last_error_code == "unsupported_language"
        other = User(auth_id=f"other-stt-{uuid4()}")
        db.add(other)
        await db.commit()
        with pytest.raises(RecordingError) as error:
            await retry_transcription(db, recording_id, other.id)
        assert getattr(error.value, "status_code", None) == 404


@pytest.mark.asyncio
async def test_retry_transcription_error_code_filtering_and_provider_update(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(settings, "audio_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "audio_encryption_key",
                        "a2tra2tra2tra2tra2tra2tra2tra2tra2tra2tra2s=")
    monkeypatch.setattr(settings, "stt_provider", "local")
    monkeypatch.setattr(settings, "stt_supported_languages", "english")
    async with AsyncSessionLocal() as db:
        user_id, recording_id, _audio = await create_stopped_recording(db, tmp_path, monkeypatch)
        job = (await db.execute(select(AIProcessingJob).where(
            AIProcessingJob.recording_id == recording_id,
            AIProcessingJob.stage == "transcription",
        ))).scalar_one()
        job.status = "failed"
        job.provider = "old_provider"
        job.last_error_code = "stt_provider_request_failed"
        await db.commit()

        # Job with different error code is ineligible when require_error_code is enforced
        with pytest.raises(RecordingError) as exc_info:
            await retry_transcription(db, recording_id, user_id, require_error_code="stt_provider_not_supported")
        assert exc_info.value.code == "transcription_retry_ineligible"

        # Update last_error_code to stt_provider_not_supported
        job.last_error_code = "stt_provider_not_supported"
        await db.commit()

        retried = await retry_transcription(db, recording_id, user_id, require_error_code="stt_provider_not_supported")
        assert retried.status == "queued"
        assert retried.provider == "local"
        assert retried.last_error_code is None
        assert retried.attempts == 0


@pytest.mark.asyncio
async def test_partial_transcript_survives_later_chunk_failure(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(settings, "audio_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "audio_encryption_key",
                        "a2tra2tra2tra2tra2tra2tra2tra2tra2tra2tra2s=")
    monkeypatch.setattr(settings, "stt_max_attempts", 1)
    monkeypatch.setattr(settings, "stt_max_chunk_duration_seconds", 1)
    monkeypatch.setattr(settings, "stt_vad_padding_ms", 0)
    monkeypatch.setattr(settings, "stt_supported_languages", "english")
    async with AsyncSessionLocal() as db:
        user_id, recording_id, _audio = await create_stopped_recording(db, tmp_path, monkeypatch)
        assert await process_next_transcription_job(db, PartialFailureProvider()) is True
        transcript = (await db.execute(select(Transcript).where(
            Transcript.recording_id == recording_id
        ))).scalar_one()
        assert transcript.status == "partial"
        assert await get_transcript(db, recording_id, user_id) is not None
        partial = await get_transcript(db, recording_id, user_id)
        assert len(partial["segments"]) == 1
        assert partial["segments"][0]["text"] == "saved portion"
        await retry_transcription(db, recording_id, user_id)
        assert await process_next_transcription_job(db, SuccessfulProvider()) is True
        completed = await get_transcript(db, recording_id, user_id)
        count = (await db.execute(select(func.count(TranscriptSegment.id)).where(
            TranscriptSegment.transcript_id == transcript.id
        ))).scalar_one()
        assert completed["status"] == "complete"
        assert completed["segments"][0]["text"] == "saved portion"
        assert count == len(completed["segments"]) and count > 1


def test_provider_requires_environment_credentials(monkeypatch):
    monkeypatch.setattr(settings, "stt_provider", "openai_whisper")
    monkeypatch.setattr(settings, "stt_api_key", None)
    with pytest.raises(STTError) as error:
        create_stt_provider()
    assert error.value.code == "stt_provider_not_configured"


@pytest.mark.asyncio
async def test_openai_provider_maps_segments_and_hides_remote_error_body(monkeypatch):
    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"language": "English", "segments": [
                {"start": 0.2, "end": 1.0, "text": " hello", "avg_logprob": -0.5}
            ]}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, content, headers):
            assert url.endswith("/audio/transcriptions")
            assert b"timestamp_granularities[]" in content
            assert "secret-test-value" in headers["Authorization"]
            return FakeResponse()

    monkeypatch.setattr("app.services.stt_provider.httpx.AsyncClient", lambda **kwargs: FakeClient())
    provider = OpenAIWhisperProvider("secret-test-value", "https://stt.invalid/v1", "whisper-1", 1)
    result = await provider.transcribe(b"audio-bytes", "audio/wav")
    assert result.language == "english"
    assert result.segments[0].confidence == pytest.approx(0.60653, rel=1e-4)

    class FailedResponse(FakeResponse):
        status_code = 401
        text = "remote response may include private detail"

    class FailedClient(FakeClient):
        async def post(self, *args, **kwargs):
            return FailedResponse()

    monkeypatch.setattr("app.services.stt_provider.httpx.AsyncClient", lambda **kwargs: FailedClient())
    with pytest.raises(STTError) as remote_error:
        await provider.transcribe(b"audio-bytes", "audio/wav")
    assert remote_error.value.retryable is False
    assert "private detail" not in str(remote_error.value)


class EmptyFirstChunkProvider:
    name = "unit_test_provider"
    model = "deterministic-test-model"

    def __init__(self):
        self.calls = 0

    async def transcribe(self, audio: bytes, content_type: str):
        self.calls += 1
        if self.calls == 1:
            return ProviderTranscript("english", [], self.model)
        return ProviderTranscript("english", [ProviderSegment(0.1, 0.7, "spoken portion", 0.9)], self.model)


class AllEmptyChunksProvider:
    name = "unit_test_provider"
    model = "deterministic-test-model"

    async def transcribe(self, audio: bytes, content_type: str):
        return ProviderTranscript("english", [], self.model)


@pytest.mark.asyncio
async def test_empty_initial_chunk_skips_and_completes_later_chunk(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(settings, "audio_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "audio_encryption_key", "a2tra2tra2tra2tra2tra2tra2tra2tra2tra2tra2s=")
    monkeypatch.setattr(settings, "stt_max_chunk_duration_seconds", 1)
    monkeypatch.setattr(settings, "stt_vad_padding_ms", 0)
    monkeypatch.setattr(settings, "stt_supported_languages", "english")
    async with AsyncSessionLocal() as db:
        user_id, recording_id, _audio = await create_stopped_recording(db, tmp_path, monkeypatch)
        assert await process_next_transcription_job(db, EmptyFirstChunkProvider()) is True
        transcript = (await db.execute(select(Transcript).where(Transcript.recording_id == recording_id))).scalar_one()
        assert transcript.status == "complete"
        output = await get_transcript(db, recording_id, user_id)
        assert len(output["segments"]) == 4
        assert output["segments"][0]["text"] == "spoken portion"


@pytest.mark.asyncio
async def test_all_chunks_empty_fails_with_non_retryable_stt_no_segments(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(settings, "audio_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "audio_encryption_key", "a2tra2tra2tra2tra2tra2tra2tra2tra2tra2tra2s=")
    monkeypatch.setattr(settings, "stt_max_attempts", 1)
    monkeypatch.setattr(settings, "stt_supported_languages", "english")
    async with AsyncSessionLocal() as db:
        user_id, recording_id, _audio = await create_stopped_recording(db, tmp_path, monkeypatch)
        assert await process_next_transcription_job(db, AllEmptyChunksProvider()) is True
        job = await get_transcription_status(db, recording_id, user_id)
        assert job.status == "failed"
        assert job.last_error_code == "stt_no_segments"


class InvalidTimestampProvider:
    name = "unit_test_provider"
    model = "deterministic-test-model"

    async def transcribe(self, audio: bytes, content_type: str):
        # Negative start timestamp
        return ProviderTranscript("english", [ProviderSegment(-0.5, 1.0, "invalid start", 0.9)], self.model)


class ExceedingChunkDurationProvider:
    name = "unit_test_provider"
    model = "deterministic-test-model"

    async def transcribe(self, audio: bytes, content_type: str):
        # Provider segment end (2.5s) exceeds chunk duration (1.0s) like Faster-Whisper on short audio
        return ProviderTranscript("english", [ProviderSegment(0.1, 2.5, "clamped speech", 0.9)], self.model)


@pytest.mark.asyncio
async def test_invalid_timestamps_fail_with_invalid_transcript_segment(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(settings, "audio_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "audio_encryption_key", "a2tra2tra2tra2tra2tra2tra2tra2tra2tra2tra2s=")
    monkeypatch.setattr(settings, "stt_max_attempts", 1)
    monkeypatch.setattr(settings, "stt_supported_languages", "english")
    async with AsyncSessionLocal() as db:
        user_id, recording_id, _audio = await create_stopped_recording(db, tmp_path, monkeypatch)
        assert await process_next_transcription_job(db, InvalidTimestampProvider()) is True
        job = await get_transcription_status(db, recording_id, user_id)
        assert job.status == "failed"
        assert job.last_error_code == "invalid_transcript_segment"


@pytest.mark.asyncio
async def test_segment_exceeding_chunk_duration_is_clamped_and_succeeds(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(settings, "audio_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "audio_encryption_key", "a2tra2tra2tra2tra2tra2tra2tra2tra2tra2tra2s=")
    monkeypatch.setattr(settings, "stt_max_chunk_duration_seconds", 1)
    monkeypatch.setattr(settings, "stt_supported_languages", "english")
    async with AsyncSessionLocal() as db:
        user_id, recording_id, _audio = await create_stopped_recording(db, tmp_path, monkeypatch)
        assert await process_next_transcription_job(db, ExceedingChunkDurationProvider()) is True
        transcript = (await db.execute(select(Transcript).where(Transcript.recording_id == recording_id))).scalar_one()
        assert transcript.status == "complete"
        output = await get_transcript(db, recording_id, user_id)
        assert len(output["segments"]) > 0
        for seg in output["segments"]:
            assert seg["end_ms"] > seg["start_ms"]
            assert seg["text"] == "clamped speech"


@pytest.mark.asyncio
async def test_audio_conversion_failed_on_corrupt_payload():
    corrupt_audio = b"\x00\x00\x00\x18ftyp3gp4corrupt_garbage_header_bytes_without_audio"
    with pytest.raises(STTError) as exc_info:
        await prepare_speech_chunks(corrupt_audio)
    assert exc_info.value.code in {"audio_conversion_failed", "audio_conversion_unavailable", "no_speech_detected"}


class MultiChunkOffsetProvider:
    name = "unit_test_provider"
    model = "deterministic-test-model"

    def __init__(self):
        self.call_count = 0

    async def transcribe(self, audio: bytes, content_type: str):
        self.call_count += 1
        return ProviderTranscript("english", [ProviderSegment(0.2, 0.8, f"chunk {self.call_count} speech", 0.95)], self.model)


@pytest.mark.asyncio
async def test_chunk_offset_combining_preserves_absolute_timestamps(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(settings, "audio_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "audio_encryption_key", "a2tra2tra2tra2tra2tra2tra2tra2tra2tra2tra2s=")
    monkeypatch.setattr(settings, "stt_max_chunk_duration_seconds", 1)
    monkeypatch.setattr(settings, "stt_vad_padding_ms", 0)
    monkeypatch.setattr(settings, "stt_supported_languages", "english")
    async with AsyncSessionLocal() as db:
        user_id, recording_id, _audio = await create_stopped_recording(db, tmp_path, monkeypatch)
        provider = MultiChunkOffsetProvider()
        assert await process_next_transcription_job(db, provider) is True
        output = await get_transcript(db, recording_id, user_id)
        assert output["status"] == "complete"
        assert len(output["segments"]) > 1
        for i in range(len(output["segments"]) - 1):
            assert output["segments"][i]["start_ms"] < output["segments"][i + 1]["start_ms"]
            assert output["segments"][i]["end_ms"] <= output["segments"][i + 1]["start_ms"] + 1000



