import base64
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.database.session import AsyncSessionLocal
from app.models import (
    AudioFile,
    AudioSourceEvent,
    AuditEvent,
    ConsentRecord,
    Recording,
    RecordingPause,
    User,
    UserProfile,
)
from app.services.audio_storage import read_encrypted_audio
from app.services.recording_service import (
    RecordingError,
    cancel_recording,
    change_audio_source,
    get_active_recording,
    get_audio_file,
    get_recording,
    pause_recording,
    recover_active_recording,
    resume_recording,
    start_recording,
    stop_recording,
    upload_audio,
)


async def _user_with_jurisdiction(db, jurisdiction="IN"):
    user = User(auth_id=f"recording-test-{uuid4()}")
    db.add(user)
    await db.flush()
    db.add(UserProfile(user_id=user.id, jurisdiction=jurisdiction))
    await db.commit()
    return user


@pytest.mark.asyncio
async def test_start_allows_recording_without_jurisdiction():
    async with AsyncSessionLocal() as db:
        user = User(auth_id=f"recording-test-{uuid4()}")
        db.add(user)
        await db.commit()

        rec = await start_recording(
            db, user.id, audio_source="phone_microphone", source_available=True,
            microphone_permission_granted=True, consent_acknowledged=True,
        )
        assert rec.id is not None
        assert rec.audio_source == "phone_microphone"
        assert rec.state == "active"


@pytest.mark.asyncio
async def test_start_rejects_denied_microphone_and_unavailable_source():
    async with AsyncSessionLocal() as db:
        user = await _user_with_jurisdiction(db)
        with pytest.raises(RecordingError) as error:
            await start_recording(
                db, user.id, audio_source="phone_microphone", source_available=True,
                microphone_permission_granted=False, consent_acknowledged=True,
            )
        assert error.value.code == "microphone_permission_required"
        with pytest.raises(RecordingError) as error:
            await start_recording(
                db, user.id, audio_source="bluetooth", source_available=False,
                microphone_permission_granted=True, consent_acknowledged=True,
            )
        assert error.value.code == "audio_source_unavailable"


@pytest.mark.asyncio
async def test_declined_consent_is_audited_without_recording():
    async with AsyncSessionLocal() as db:
        user = await _user_with_jurisdiction(db)
        with pytest.raises(RecordingError) as error:
            await start_recording(
                db, user.id, audio_source="phone_microphone", source_available=True,
                microphone_permission_granted=True, consent_acknowledged=False,
            )
        assert error.value.code == "consent_declined"
        assert (await db.execute(select(Recording))).scalars().all() == []
        event_types = (await db.execute(select(AuditEvent.event_type))).scalars().all()
        assert "consent.prompt_shown" in event_types
        assert "consent.declined" in event_types


@pytest.mark.asyncio
async def test_recording_lifecycle_encrypted_audio_and_user_scoping(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(settings, "audio_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "audio_encryption_key", base64.urlsafe_b64encode(b"k" * 32).decode())

    async with AsyncSessionLocal() as db:
        owner = await _user_with_jurisdiction(db)
        other = await _user_with_jurisdiction(db)
        owner_id = owner.id
        other_id = other.id
        recording = await start_recording(
            db, owner_id, audio_source="bluetooth", source_available=True,
            microphone_permission_granted=True, consent_acknowledged=True,
        )
        recording_id = recording.id
        assert recording.state == "active"
        assert recording.status == "active"
        assert (await db.execute(select(ConsentRecord).where(
            ConsentRecord.recording_id == recording_id
        ))).scalar_one().jurisdiction == "IN"
        assert await get_recording(db, recording_id, other_id) is None

        with pytest.raises(RecordingError, match="already active"):
            await start_recording(
                db, owner_id, audio_source="phone_microphone", source_available=True,
                microphone_permission_granted=True, consent_acknowledged=True,
            )

        with pytest.raises(RecordingError, match="Upload the captured audio"):
            await stop_recording(db, recording_id, owner_id)

        await change_audio_source(db, recording_id, owner_id, "phone_microphone", True)
        await pause_recording(db, recording_id, owner_id)
        await resume_recording(db, recording_id, owner_id)
        pauses = (await db.execute(select(RecordingPause).where(
            RecordingPause.recording_id == recording_id
        ))).scalars().all()
        assert len(pauses) == 1 and pauses[0].resumed_at is not None

        payload = b"captured audio fixture"
        audio = await upload_audio(db, recording_id, owner_id, payload, "audio/wav", 1200)
        assert await get_audio_file(db, recording_id, other_id) is None
        encrypted_file = tmp_path / audio.storage_ref
        assert encrypted_file.exists()
        assert encrypted_file.read_bytes() != payload
        assert read_encrypted_audio(audio.storage_ref) == payload

        stopped = await stop_recording(db, recording_id, owner_id)
        assert stopped.state == "processing"
        assert stopped.duration_ms == 1200
        assert (await db.execute(select(AudioSourceEvent).where(
            AudioSourceEvent.recording_id == recording_id
        ))).scalar_one().to_source == "phone_microphone"
        events = (await db.execute(select(AuditEvent.event_type))).scalars().all()
        assert {"recording.started", "recording.paused", "recording.resumed",
                "recording.stopped", "recording.audio_source_changed", "audio.stored"} <= set(events)


@pytest.mark.asyncio
async def test_invalid_state_transition_is_rejected():
    async with AsyncSessionLocal() as db:
        user = await _user_with_jurisdiction(db)
        recording = await start_recording(
            db, user.id, audio_source="phone_microphone", source_available=True,
            microphone_permission_granted=True, consent_acknowledged=True,
        )
        await pause_recording(db, recording.id, user.id)
        with pytest.raises(RecordingError, match="Cannot pause"):
            await pause_recording(db, recording.id, user.id)
        assert await get_recording(db, recording.id, user.id) is not None


@pytest.mark.asyncio
async def test_abandoned_recording_recovery_without_audio_unblocks_user():
    """Verify that an abandoned recording without audio is safely recovered/cancelled,
    preserving database records, and immediately allowing the user to start a new recording."""
    async with AsyncSessionLocal() as db:
        user = await _user_with_jurisdiction(db)
        user_id = user.id
        rec1 = await start_recording(
            db, user_id, audio_source="phone_microphone", source_available=True,
            microphone_permission_granted=True, consent_acknowledged=True,
        )
        rec1_id = rec1.id
        assert rec1.state == "active"

        # Duplicate start attempt must be rejected with active recording error
        with pytest.raises(RecordingError, match="already active") as exc_info:
            await start_recording(
                db, user_id, audio_source="phone_microphone", source_available=True,
                microphone_permission_granted=True, consent_acknowledged=True,
            )
        assert exc_info.value.code == "recording_already_active"
        assert f"#{rec1_id}" in exc_info.value.message

        # Stop without audio must be rejected
        with pytest.raises(RecordingError) as exc_stop:
            await stop_recording(db, rec1_id, user_id)
        assert exc_stop.value.code == "audio_required"

        # Verify get_active_recording finds it
        active_rec = await get_active_recording(db, user_id)
        assert active_rec is not None
        assert active_rec.id == rec1_id

        # Attempting to recover empty session raises no_audio_to_recover
        with pytest.raises(RecordingError) as exc_rec:
            await recover_active_recording(db, user_id, rec1_id)
        assert exc_rec.value.code == "no_audio_to_recover"
        assert f"#{rec1_id}" in exc_rec.value.message

        # Session remains open on server until explicitly discarded
        assert (await get_active_recording(db, user_id)).id == rec1_id

        # Discard abandoned recording safely
        discarded = await cancel_recording(db, rec1_id, user_id, reason="abandoned")
        assert discarded.id == rec1_id
        assert discarded.state == "failed"
        assert discarded.status == "failed"
        assert discarded.duration_ms == 0

        # Repeating discard is idempotent
        repeat_discard = await cancel_recording(db, rec1_id, user_id)
        assert repeat_discard.id == rec1_id
        assert repeat_discard.state == "failed"

        # No active recording remains
        assert await get_active_recording(db, user_id) is None

        # User can now start a new recording without conflict!
        rec2 = await start_recording(
            db, user_id, audio_source="phone_microphone", source_available=True,
            microphone_permission_granted=True, consent_acknowledged=True,
        )
        assert rec2.id is not None
        assert rec2.id != rec1.id
        assert rec2.state == "active"



@pytest.mark.asyncio
async def test_abandoned_recording_recovery_with_audio_preserves_audio_and_processes(monkeypatch, tmp_path: Path):
    """Verify that an active recording with uploaded audio is finalized and processed on recovery,
    preserving the audio payload and queuing transcription."""
    monkeypatch.setattr(settings, "audio_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "audio_encryption_key", base64.urlsafe_b64encode(b"k" * 32).decode())

    async with AsyncSessionLocal() as db:
        user = await _user_with_jurisdiction(db)
        rec = await start_recording(
            db, user.id, audio_source="phone_microphone", source_available=True,
            microphone_permission_granted=True, consent_acknowledged=True,
        )
        payload = b"precious recorded audio that must not be lost"
        audio = await upload_audio(db, rec.id, user.id, payload, "audio/wav", 5500)
        assert audio.id is not None

        # Recovery should detect audio and finalize it
        recovered = await recover_active_recording(db, user.id, rec.id)
        assert recovered.id == rec.id
        assert recovered.state == "processing"
        assert recovered.duration_ms == 5500

        # Audio file is preserved on disk
        assert read_encrypted_audio(audio.storage_ref) == payload

