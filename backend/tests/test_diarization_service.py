from datetime import datetime, timezone
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import get_current_user
from app.database.session import get_db
from app.database.session import AsyncSessionLocal
from app.main import app
from app.models import (AIProcessingJob, AudioFile, AuditEvent, Conversation, Person, Recording,
                        Speaker, Transcript, TranscriptSegment, User)
from app.services.audio_storage import store_encrypted_audio
from app.services.diarization_provider import DiarizationError, SpeakerAssignment
from app.services.diarization_provider import create_diarization_provider
from app.services.diarization_service import (get_diarization_status,
                                              process_next_diarization_job, relabel_speaker)
from app.services.encryption import encrypt_bytes
from app.services.recording_service import RecordingError


class FixtureDiarizer:
    name = "fixture_diarizer"
    model = "fixture-v1"

    def __init__(self, assignments=None, error=None):
        self.assignments = assignments or []
        self.error = error

    async def diarize(self, audio, content_type, segments):
        assert audio == b"encrypted-source-audio-after-decryption"
        assert content_type == "audio/wav"
        assert len(segments) == 2
        if self.error:
            raise self.error
        if callable(self.assignments):
            return self.assignments(segments)
        return self.assignments


def test_diarization_provider_requires_explicit_environment_configuration(monkeypatch):
    monkeypatch.setattr(settings, "diarization_provider", "http_json")
    monkeypatch.setattr(settings, "diarization_api_base_url", None)
    monkeypatch.setattr(settings, "diarization_api_key", None)
    monkeypatch.setattr(settings, "diarization_model", "")
    with pytest.raises(DiarizationError) as error:
        create_diarization_provider()
    assert error.value.code == "diarization_provider_not_configured"


async def setup_diarization(db, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "audio_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "audio_encryption_key", "a2tra2tra2tra2tra2tra2tra2tra2tra2tra2tra2s=")
    owner = User(auth_id=f"diarization-owner-{uuid4()}")
    other = User(auth_id=f"diarization-other-{uuid4()}")
    db.add_all([owner, other])
    await db.flush()
    now = datetime.now(timezone.utc)
    recording = Recording(user_id=owner.id, state="ready_for_review", status="ready_for_review",
                          started_at=now, created_at=now, updated_at=now)
    db.add(recording)
    await db.flush()
    storage_ref = store_encrypted_audio(b"encrypted-source-audio-after-decryption")
    db.add(AudioFile(recording_id=recording.id, storage_ref=storage_ref,
                     encryption_key_ref="env:AUDIO_ENCRYPTION_KEY", content_type="audio/wav",
                     size_bytes=39, duration_ms=1200, created_at=now))
    conversation = Conversation(user_id=owner.id, recording_id=recording.id,
                                title="Conversation", occurred_at=now)
    db.add(conversation)
    await db.flush()
    transcript = Transcript(recording_id=recording.id, conversation_id=conversation.id,
                            language="english", detected_languages='["english"]', status="complete",
                            encryption_key_ref="env:AUDIO_ENCRYPTION_KEY", created_at=now,
                            updated_at=now)
    db.add(transcript)
    await db.flush()
    for index, (start, end, text) in enumerate([(0, 600, "First words"), (600, 1200, "Second words")]):
        aad = f"pcma-transcript-{transcript.id}-0-{index}".encode()
        db.add(TranscriptSegment(transcript_id=transcript.id, chunk_index=0,
                                 segment_index=index, start_ms=start, end_ms=end,
                                 text_ciphertext=encrypt_bytes(text.encode(), aad),
                                 confidence=0.9, low_confidence=False))
    job = AIProcessingJob(recording_id=recording.id, stage="diarization", status="queued",
                          provider="fixture_diarizer", model_used="fixture-v1", attempts=0,
                          max_attempts=3, available_at=now, created_at=now, updated_at=now)
    db.add(job)
    await db.commit()
    return owner.id, other.id, recording.id, conversation.id, job.id


@pytest.mark.asyncio
async def test_diarization_groups_multi_speaker_segments_and_keeps_output_provisional(
    tmp_path, monkeypatch,
):
    async with AsyncSessionLocal() as db:
        owner_id, other_id, recording_id, conversation_id, job_id = await setup_diarization(db, tmp_path, monkeypatch)
        provider = FixtureDiarizer(lambda segments: [
            SpeakerAssignment(segments[0].id, "provider-a", .91),
            SpeakerAssignment(segments[1].id, "provider-b", .88),
        ])
        assert await process_next_diarization_job(db, provider)
        speakers = list((await db.execute(select(Speaker).where(
            Speaker.conversation_id == conversation_id).order_by(Speaker.id))).scalars())
        segments = list((await db.execute(select(TranscriptSegment).order_by(
            TranscriptSegment.segment_index))).scalars())
        job = (await db.execute(select(AIProcessingJob).where(AIProcessingJob.id == job_id))).scalar_one()
        events = (await db.execute(select(AuditEvent.event_type).where(
            AuditEvent.user_id == owner_id))).scalars().all()
        assert [speaker.label for speaker in speakers] == ["Speaker 1", "Speaker 2"]
        assert all(not speaker.confirmed for speaker in speakers)
        assert [segment.speaker_id for segment in segments] == [speaker.id for speaker in speakers]
        assert all(not segment.speaker_uncertain for segment in segments)
        assert job.status == "complete"
        assert "diarization.completed" in events
        assert await get_diarization_status(db, recording_id, owner_id) is not None
        assert await get_diarization_status(db, recording_id, other_id) is None


@pytest.mark.asyncio
async def test_single_speaker_is_assigned_to_user_and_low_confidence_is_uncertain(
    tmp_path, monkeypatch,
):
    async with AsyncSessionLocal() as db:
        _, _, recording_id, conversation_id, _ = await setup_diarization(db, tmp_path, monkeypatch)
        assert await process_next_diarization_job(db, FixtureDiarizer(lambda segments: [
            SpeakerAssignment(segments[0].id, "one", .95),
            SpeakerAssignment(segments[1].id, "one", .9),
        ]))
        speaker = (await db.execute(select(Speaker).where(
            Speaker.conversation_id == conversation_id))).scalar_one()
        assert speaker.is_user is True
        assert speaker.label == "You"
        assert [s.speaker_id for s in (await db.execute(select(TranscriptSegment))).scalars()] == [speaker.id, speaker.id]

    async with AsyncSessionLocal() as db:
        _, _, recording_id, conversation_id, _ = await setup_diarization(db, tmp_path, monkeypatch)
        assert await process_next_diarization_job(db, FixtureDiarizer(lambda segments: [
            SpeakerAssignment(segments[0].id, "one", .2),
        ]))
        uncertain = (await db.execute(select(Speaker).where(
            Speaker.conversation_id == conversation_id))).scalar_one()
        transcript_id = (await db.execute(select(Transcript.id).where(
            Transcript.recording_id == recording_id))).scalar_one()
        segments = list((await db.execute(select(TranscriptSegment).where(
            TranscriptSegment.transcript_id == transcript_id).order_by(
                TranscriptSegment.segment_index))).scalars())
        assert uncertain.uncertain is True
        assert segments[0].speaker_uncertain is True
        assert segments[1].speaker_uncertain is True


@pytest.mark.asyncio
async def test_relabel_is_user_scoped_validates_person_and_audits(tmp_path, monkeypatch):
    async with AsyncSessionLocal() as db:
        owner_id, other_id, recording_id, conversation_id, _ = await setup_diarization(db, tmp_path, monkeypatch)
        speaker = Speaker(conversation_id=conversation_id, label="Speaker 1", confirmed=False)
        own_person = Person(user_id=owner_id, name="Ravi")
        foreign_person = Person(user_id=other_id, name="Private person")
        db.add_all([speaker, own_person, foreign_person])
        await db.commit()
        await db.refresh(speaker)
        await db.refresh(own_person)
        await db.refresh(foreign_person)
        with pytest.raises(RecordingError) as hidden:
            await relabel_speaker(db, recording_id, speaker.id, other_id, "Other")
        assert hidden.value.status_code == 404
        with pytest.raises(RecordingError) as foreign_person_error:
            await relabel_speaker(db, recording_id, speaker.id, owner_id, "Ravi", foreign_person.id)
        assert foreign_person_error.value.code == "person_not_found"
        updated = await relabel_speaker(db, recording_id, speaker.id, owner_id, "Ravi", own_person.id)
        assert updated.confirmed is True
        assert updated.person_id == own_person.id
        assert (await db.execute(select(AuditEvent).where(
            AuditEvent.event_type == "speaker.relabeled",
            AuditEvent.user_id == owner_id))).scalar_one()


@pytest.mark.asyncio
async def test_retryable_provider_failure_uses_bounded_job_retry(tmp_path, monkeypatch):
    async with AsyncSessionLocal() as db:
        _, _, _, _, job_id = await setup_diarization(db, tmp_path, monkeypatch)
        error = DiarizationError("provider_busy", "busy", retryable=True)
        assert await process_next_diarization_job(db, FixtureDiarizer(error=error))
        job = (await db.execute(select(AIProcessingJob).where(AIProcessingJob.id == job_id))).scalar_one()
        assert job.status == "queued"
        assert job.attempts == 1
        assert job.last_error_code == "provider_busy"
        events = (await db.execute(select(AuditEvent.event_type).where(
            AuditEvent.event_type == "diarization.retry_scheduled"))).scalars().all()
        assert events


@pytest.mark.asyncio
async def test_speaker_label_api_is_user_scoped_and_returns_diarization_fields(tmp_path, monkeypatch):
    async with AsyncSessionLocal() as db:
        owner_id, other_id, recording_id, conversation_id, _ = await setup_diarization(db, tmp_path, monkeypatch)
        speaker = Speaker(conversation_id=conversation_id, label="Speaker 1", confirmed=False)
        person = Person(user_id=owner_id, name="Ravi")
        db.add_all([speaker, person])
        await db.commit()
        await db.refresh(speaker)
        await db.refresh(person)
        owner = (await db.execute(select(User).where(User.id == owner_id))).scalar_one()
        other = (await db.execute(select(User).where(User.id == other_id))).scalar_one()

    async def request_as(user, method, path, **kwargs):
        async def override_db():
            async with AsyncSessionLocal() as db:
                yield db
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                         base_url="http://test") as client:
                return await client.request(method, path, **kwargs)
        finally:
            app.dependency_overrides.clear()

    path = f"/v1/recordings/{recording_id}/speakers/{speaker.id}"
    hidden = await request_as(other, "PATCH", path, json={"label": "Other"})
    assert hidden.status_code == 404
    updated = await request_as(owner, "PATCH", path,
                               json={"label": "Ravi", "person_id": person.id})
    assert updated.status_code == 200
    assert updated.json()["label"] == "Ravi"
    assert updated.json()["person_id"] == person.id
    renamed = await request_as(owner, "PATCH", path, json={"label": "Ravi Kumar"})
    assert renamed.status_code == 200
    assert renamed.json()["person_id"] == person.id
    transcript = await request_as(owner, "GET", f"/v1/recordings/{recording_id}/transcript")
    assert transcript.status_code == 200
    assert transcript.json()["conversation_id"] == conversation_id
    assert transcript.json()["speakers"][0]["confirmed"] is True


def test_local_pyannote_provider_creation_and_factory(monkeypatch):
    monkeypatch.setattr(settings, "diarization_provider", "local")
    provider = create_diarization_provider()
    from app.services.diarization_provider import LocalPyannoteDiarizationProvider
    assert isinstance(provider, LocalPyannoteDiarizationProvider)
    assert provider.name == "local"

    pyannote_provider = create_diarization_provider("pyannote")
    assert isinstance(pyannote_provider, LocalPyannoteDiarizationProvider)


@pytest.mark.asyncio
async def test_local_pyannote_provider_diarize_mocked(monkeypatch):
    from app.services.diarization_provider import DiarizationInputSegment, LocalPyannoteDiarizationProvider

    class MockTurn:
        def __init__(self, start, end):
            self.start = start
            self.end = end

    class MockDiarizationResult:
        def itertracks(self, yield_label=True):
            return [
                (MockTurn(0.0, 0.5), "t1", "SPEAKER_00"),
                (MockTurn(0.6, 1.2), "t2", "SPEAKER_01"),
            ]

    def fake_pipeline(file_dict):
        return MockDiarizationResult()

    provider = LocalPyannoteDiarizationProvider(model="mock-model", device="cpu")
    monkeypatch.setattr(provider, "_load_pipeline", lambda: fake_pipeline)

    segments = [
        DiarizationInputSegment(id=101, start_ms=0, end_ms=500, text="First speaker"),
        DiarizationInputSegment(id=102, start_ms=600, end_ms=1200, text="Second speaker"),
    ]

    assignments = await provider.diarize(b"fake-wav-bytes", "audio/wav", segments)
    assert len(assignments) == 2
    assert assignments[0].segment_id == 101
    assert assignments[0].speaker_label == "SPEAKER_00"
    assert assignments[0].confidence == pytest.approx(1.0)
    assert assignments[1].segment_id == 102
    assert assignments[1].speaker_label == "SPEAKER_01"
    assert assignments[1].confidence == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_local_pyannote_provider_error_handling(monkeypatch):
    import sys, types
    try:
        from pyannote.audio import Pipeline
    except ImportError:
        fake_pyannote_audio = types.ModuleType("pyannote.audio")
        class FakePipeline:
            @classmethod
            def from_pretrained(cls, *args, **kwargs):
                pass
        fake_pyannote_audio.Pipeline = FakePipeline
        sys.modules["pyannote.audio"] = fake_pyannote_audio
        Pipeline = FakePipeline
    from app.services.diarization_provider import DiarizationError, LocalPyannoteDiarizationProvider

    provider = LocalPyannoteDiarizationProvider(model="pyannote/speaker-diarization-3.1")

    def raise_gated_error(*args, **kwargs):
        raise Exception("Gated repo access denied: 401 Unauthorized for model")

    monkeypatch.setattr(Pipeline, "from_pretrained", raise_gated_error)
    with pytest.raises(DiarizationError) as exc_info:
        provider._load_pipeline()
    assert exc_info.value.code == "diarization_credentials_missing"
    assert exc_info.value.retryable is False

    def raise_network_error(*args, **kwargs):
        raise Exception("Connection timeout downloading model weights")

    monkeypatch.setattr(Pipeline, "from_pretrained", raise_network_error)
    provider2 = LocalPyannoteDiarizationProvider(model="pyannote/speaker-diarization-3.1")
    with pytest.raises(DiarizationError) as exc_info2:
        provider2._load_pipeline()
    assert exc_info2.value.code == "diarization_model_download_failed"
    assert exc_info2.value.retryable is True

