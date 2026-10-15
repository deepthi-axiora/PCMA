import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("pcma.recording_service")

from app.models import (
    AudioFile,
    AudioSourceEvent,
    AuditEvent,
    ConsentRecord,
    Recording,
    RecordingPause,
    UserProfile,
)
from app.core.config import settings
from app.repositories.transcription_repository import create_transcription_job
from app.services.audio_storage import store_encrypted_audio

ALLOWED_SOURCES = {"phone_microphone", "wired_headset", "bluetooth", "external_microphone"}


class RecordingError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _event(db: AsyncSession, user_id: int, event_type: str, recording_id: int | None,
           **metadata: str | int | bool) -> None:
    db.add(AuditEvent(
        user_id=user_id,
        event_type=event_type,
        entity_type="Recording" if recording_id is not None else "Consent",
        entity_id=recording_id,
        metadata_json=json.dumps(metadata, separators=(",", ":")),
    ))


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


async def _owned_recording(db: AsyncSession, recording_id: int, user_id: int) -> Recording | None:
    result = await db.execute(
        select(Recording).where(Recording.id == recording_id, Recording.user_id == user_id)
        .with_for_update()
    )
    return result.scalar_one_or_none()


async def start_recording(
    db: AsyncSession,
    user_id: int,
    *,
    audio_source: str,
    source_available: bool,
    microphone_permission_granted: bool,
    consent_acknowledged: bool,
) -> Recording:
    if not microphone_permission_granted:
        raise RecordingError("microphone_permission_required", "Microphone permission is required", 403)
    if audio_source not in ALLOWED_SOURCES or not source_available:
        raise RecordingError("audio_source_unavailable", "Select an available audio input", 422)

    profile = (await db.execute(select(UserProfile).where(UserProfile.user_id == user_id)))
    profile = profile.scalar_one_or_none()
    jurisdiction = profile.jurisdiction if profile else None

    now = datetime.now(timezone.utc)
    _event(db, user_id, "consent.prompt_shown", None, jurisdiction=jurisdiction)
    if not consent_acknowledged:
        _event(db, user_id, "consent.declined", None, jurisdiction=jurisdiction)
        await db.commit()
        raise RecordingError("consent_declined", "Recording was not started because consent was declined", 400)

    active = await db.execute(select(Recording.id).where(
        Recording.user_id == user_id, Recording.state.in_(("active", "paused"))
    ))
    active_id = active.scalar_one_or_none()
    if active_id is not None:
        await db.rollback()
        raise RecordingError("recording_already_active", f"A recording (#{active_id}) is already active for this user")

    recording = Recording(user_id=user_id, state="active", audio_source=audio_source,
                          started_at=now, created_at=now, updated_at=now)
    db.add(recording)
    await db.flush()
    db.add(ConsentRecord(
        recording_id=recording.id,
        jurisdiction=jurisdiction,
        prompt_shown=True,
        acknowledged_at=now,
    ))
    _event(db, user_id, "recording.started", recording.id, state="active", audio_source=audio_source)
    _event(db, user_id, "consent.acknowledged", recording.id, jurisdiction=jurisdiction)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        err_str = str(exc).lower()
        if "uq_recordings_one_open_per_user" in err_str or ("unique" in err_str and "recordings" in err_str):
            raise RecordingError("recording_already_active", "Another recording is already active") from exc
        logger.error("Database integrity error during start_recording: %s", exc, exc_info=True)
        raise
    await db.refresh(recording)
    return recording


async def list_recordings(db: AsyncSession, user_id: int) -> list[Recording]:
    result = await db.execute(select(Recording).where(Recording.user_id == user_id)
                              .order_by(Recording.started_at.desc()))
    return list(result.scalars().all())


async def get_recording(db: AsyncSession, recording_id: int, user_id: int) -> Recording | None:
    return await _owned_recording(db, recording_id, user_id)


async def upload_audio(
    db: AsyncSession, recording_id: int, user_id: int, content: bytes,
    content_type: str, duration_ms: int | None,
) -> AudioFile:
    recording = await _owned_recording(db, recording_id, user_id)
    if recording is None:
        raise RecordingError("recording_not_found", "Recording not found", 404)
    if recording.state not in {"active", "paused"}:
        raise RecordingError("invalid_recording_state", "Audio can only be uploaded to an open recording")
    existing = (await db.execute(select(AudioFile).where(AudioFile.recording_id == recording_id)))
    if existing.scalar_one_or_none() is not None:
        raise RecordingError("audio_already_uploaded", "Audio has already been uploaded for this recording")
    if not content:
        raise RecordingError("empty_audio", "Audio upload is empty", 422)
    try:
        storage_ref = store_encrypted_audio(content)
    except Exception:
        await db.rollback()
        raise
    audio = AudioFile(
        recording_id=recording.id,
        storage_ref=storage_ref,
        encryption_key_ref="env:AUDIO_ENCRYPTION_KEY",
        content_type=content_type,
        size_bytes=len(content),
        duration_ms=duration_ms,
    )
    db.add(audio)
    _event(db, user_id, "audio.stored", recording.id, size_bytes=len(content))
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        from app.services.audio_storage import delete_audio
        delete_audio(storage_ref)
        raise
    await db.refresh(audio)
    return audio


async def get_audio_file(db: AsyncSession, recording_id: int, user_id: int) -> AudioFile | None:
    result = await db.execute(
        select(AudioFile).join(Recording).where(
            Recording.id == recording_id, Recording.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def _transition(db: AsyncSession, recording_id: int, user_id: int,
                      expected: str, target: str, event_type: str) -> Recording:
    recording = await _owned_recording(db, recording_id, user_id)
    if recording is None:
        raise RecordingError("recording_not_found", "Recording not found", 404)
    if recording.state != expected:
        raise RecordingError("invalid_recording_state", f"Cannot {event_type.rsplit('.', 1)[-1]} a recording in {recording.state} state")
    now = datetime.now(timezone.utc)
    recording.state = target
    recording.status = target
    recording.updated_at = now
    if target == "paused":
        db.add(RecordingPause(recording_id=recording.id, paused_at=now))
    elif target == "active":
        pause = (await db.execute(select(RecordingPause).where(
            RecordingPause.recording_id == recording.id, RecordingPause.resumed_at.is_(None)
        ).order_by(RecordingPause.paused_at.desc()).limit(1).with_for_update())).scalar_one()
        pause.resumed_at = now
    _event(db, user_id, event_type, recording.id, from_state=expected, to_state=target)
    await db.commit()
    await db.refresh(recording)
    return recording


async def pause_recording(db: AsyncSession, recording_id: int, user_id: int) -> Recording:
    return await _transition(db, recording_id, user_id, "active", "paused", "recording.paused")


async def resume_recording(db: AsyncSession, recording_id: int, user_id: int) -> Recording:
    return await _transition(db, recording_id, user_id, "paused", "active", "recording.resumed")


async def stop_recording(db: AsyncSession, recording_id: int, user_id: int) -> Recording:
    recording = await _owned_recording(db, recording_id, user_id)
    if recording is None:
        raise RecordingError("recording_not_found", "Recording not found", 404)
    if recording.state not in {"active", "paused"}:
        raise RecordingError("invalid_recording_state", f"Cannot stop a recording in {recording.state} state")
    audio = (await db.execute(select(AudioFile).where(AudioFile.recording_id == recording.id))).scalar_one_or_none()
    if audio is None:
        raise RecordingError("audio_required", "Upload the captured audio before stopping the recording", 422)
    now = datetime.now(timezone.utc)
    pauses = (await db.execute(select(RecordingPause).where(
        RecordingPause.recording_id == recording.id
    ))).scalars().all()
    paused_ms = 0
    for pause in pauses:
        end = _utc(pause.resumed_at) if pause.resumed_at else now
        paused_ms += max(0, int((end - _utc(pause.paused_at)).total_seconds() * 1000))
    recording.state = "processing"
    recording.status = "processing"
    recording.stopped_at = now
    if recording.started_at is None:
        raise RecordingError("invalid_recording_state", "Recording start time is missing")
    recording.duration_ms = max(0, int((now - _utc(recording.started_at)).total_seconds() * 1000) - paused_ms)
    recording.updated_at = now
    if audio.duration_ms is not None:
        recording.duration_ms = audio.duration_ms
    _event(db, user_id, "recording.stopped", recording.id, state="processing")
    await create_transcription_job(db, recording.id, settings.stt_provider,
                                   settings.stt_max_attempts)
    _event(db, user_id, "transcription.queued", recording.id, stage="transcription")
    await db.commit()
    await db.refresh(recording)
    return recording


async def change_audio_source(db: AsyncSession, recording_id: int, user_id: int,
                              new_source: str, source_available: bool) -> Recording:
    recording = await _owned_recording(db, recording_id, user_id)
    if recording is None:
        raise RecordingError("recording_not_found", "Recording not found", 404)
    if recording.state != "active":
        raise RecordingError("invalid_recording_state", "Audio source can only change while recording")
    if new_source not in ALLOWED_SOURCES or not source_available:
        raise RecordingError("audio_source_unavailable", "Selected audio input is unavailable", 422)
    old_source = recording.audio_source
    now = datetime.now(timezone.utc)
    recording.audio_source = new_source
    recording.updated_at = now
    db.add(AudioSourceEvent(recording_id=recording.id, from_source=old_source,
                            to_source=new_source, changed_at=now))
    _event(db, user_id, "recording.audio_source_changed", recording.id,
           from_source=old_source, to_source=new_source)
    await db.commit()
    await db.refresh(recording)
    return recording


async def get_active_recording(db: AsyncSession, user_id: int) -> Recording | None:
    result = await db.execute(
        select(Recording).where(
            Recording.user_id == user_id,
            Recording.state.in_(("active", "paused")),
        ).order_by(Recording.started_at.desc())
    )
    return result.scalar_one_or_none()


async def cancel_recording(
    db: AsyncSession, recording_id: int, user_id: int, reason: str = "abandoned"
) -> Recording:
    recording = await _owned_recording(db, recording_id, user_id)
    if recording is None:
        raise RecordingError("recording_not_found", "Recording not found", 404)

    # Idempotent handling: already cancelled session safely returns current state
    if recording.state == "failed":
        return recording

    if recording.state not in {"active", "paused"}:
        raise RecordingError(
            "invalid_recording_state",
            f"Cannot discard recording in '{recording.state}' state. Only active or paused sessions can be discarded.",
            400,
        )

    now = datetime.now(timezone.utc)
    audio = (await db.execute(select(AudioFile).where(AudioFile.recording_id == recording.id))).scalar_one_or_none()

    recording.state = "failed"
    recording.status = "failed"
    recording.stopped_at = now
    recording.duration_ms = audio.duration_ms if audio and audio.duration_ms is not None else 0
    recording.updated_at = now

    _event(db, user_id, "recording.cancelled", recording.id, reason=reason, has_audio=audio is not None)
    await db.commit()
    await db.refresh(recording)
    return recording


async def recover_active_recording(
    db: AsyncSession, user_id: int, recording_id: int | None = None
) -> Recording:
    """Safe recovery mechanism for active/abandoned recordings.
    - If audio was uploaded: finalizes and triggers transcription to preserve audio.
    - If no audio was uploaded: returns a clear explanation that there is no audio to recover
      and directs the user/client to discard the session.
    - If already processed/completed: safely returns the existing recording idempotently.
    Preserves all existing records and audit history.
    """
    if recording_id is not None:
        recording = await _owned_recording(db, recording_id, user_id)
    else:
        recording = await get_active_recording(db, user_id)

    if recording is None:
        raise RecordingError("recording_not_found", "No active or paused recording found to recover", 404)

    # Idempotent handling for already-recovered or completed sessions
    if recording.state in {"processing", "ready_for_review", "completed"}:
        return recording

    if recording.state == "failed":
        raise RecordingError(
            "recording_cancelled",
            f"Recording #{recording.id} has already been cancelled and cannot be recovered.",
            400,
        )

    if recording.state not in {"active", "paused"}:
        raise RecordingError(
            "invalid_recording_state",
            f"Recording #{recording.id} is in '{recording.state}' state and cannot be recovered.",
            400,
        )

    audio = (await db.execute(select(AudioFile).where(AudioFile.recording_id == recording.id))).scalar_one_or_none()

    if audio is not None:
        # Audio was uploaded: preserve and finalize by processing it
        return await stop_recording(db, recording.id, user_id)
    else:
        # No audio was ever uploaded: do not fake recovery. Return actionable error directing to discard.
        raise RecordingError(
            "no_audio_to_recover",
            f"No audio was recorded for session #{recording.id}. Discard it to begin a clean session.",
            400,
        )


