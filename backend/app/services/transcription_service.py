import asyncio
import json
import logging
import math
import traceback
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from cryptography.exceptions import InvalidTag

from app.core.config import settings
from app.models import (AIProcessingJob, AudioFile, AuditEvent, Conversation, Recording,
                        Speaker, Transcript, TranscriptSegment, TranscriptEditHistory)
from app.repositories.transcription_repository import (
    claim_next_transcription_job,
    get_job_for_owner,
    get_transcript_for_owner,
)
from app.services.audio_preprocessing import prepare_speech_chunks
from app.services.audio_storage import AudioStorageNotConfigured, read_encrypted_audio
from app.services.encryption import EncryptionKeyUnavailable, decrypt_bytes, encrypt_bytes
from app.services.recording_service import RecordingError
from app.services.stt_provider import (
    ProviderTranscript,
    SpeechToTextProvider,
    STTError,
    create_stt_provider,
)

logger = logging.getLogger("pcma.transcription_service")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _audit(db: AsyncSession, user_id: int, recording_id: int, event_type: str,
           **metadata: str | int | bool) -> None:
    db.add(AuditEvent(
        user_id=user_id,
        event_type=event_type,
        entity_type="Recording",
        entity_id=recording_id,
        metadata_json=json.dumps(metadata, separators=(",", ":")),
    ))


def _supported_languages() -> set[str]:
    return {language.strip().lower() for language in settings.stt_supported_languages.split(",")
            if language.strip()}


async def process_next_transcription_job(
    db: AsyncSession,
    provider: SpeechToTextProvider | None = None,
) -> bool:
    job = await claim_next_transcription_job(db, settings.stt_job_lease_seconds)
    if job is None:
        await db.rollback()
        return False
    job_id = job.id
    recording_id = job.recording_id
    await db.commit()
    logger.info("transcription_job_claimed job_id=%d recording_id=%d stage=%s provider=%s "
                "attempt=%d", job_id, recording_id, job.stage, job.provider, job.attempts)
    try:
        job = (await db.execute(select(AIProcessingJob).where(AIProcessingJob.id == job_id)
                                .with_for_update())).scalar_one()
        recording = (await db.execute(select(Recording).where(Recording.id == recording_id)
                                      .with_for_update())).scalar_one()
        audio_file = (await db.execute(select(AudioFile).where(
            AudioFile.recording_id == recording_id
        ))).scalar_one_or_none()
        if audio_file is None:
            raise STTError("audio_file_missing", "Recording audio is unavailable for transcription",
                           retryable=False)
        logger.info("transcription_audio_metadata job_id=%d recording_id=%d content_type=%s "
                    "stored_byte_length=%d duration_ms=%s", job_id, recording_id,
                    audio_file.content_type, audio_file.size_bytes, audio_file.duration_ms)
        if provider is None:
            provider = create_stt_provider(job.provider, job.model_used)
        job.model_used = provider.model
        _audit(db, recording.user_id, recording.id, "transcription.started",
               provider=job.provider, model=job.model_used, attempt=job.attempts)
        await db.commit()
        transcript_result = await asyncio.to_thread(read_encrypted_audio, audio_file.storage_ref)
        logger.info("transcription_audio_decrypted job_id=%d recording_id=%d byte_length=%d",
                    job_id, recording_id, len(transcript_result))
        logger.info("transcription_preprocessing_started job_id=%d recording_id=%d",
                    job_id, recording_id)
        chunks, _duration_ms = await prepare_speech_chunks(transcript_result)
        logger.info("transcription_preprocessing_completed job_id=%d recording_id=%d "
                    "duration_ms=%d chunk_count=%d chunk_durations_ms=%s", job_id,
                    recording_id, _duration_ms, len(chunks),
                    ",".join(str(chunk.end_ms - chunk.start_ms) for chunk in chunks))

        transcript = (await db.execute(select(Transcript).where(
            Transcript.recording_id == recording_id
        ).with_for_update())).scalar_one_or_none()
        if transcript is None:
            transcript = Transcript(
                recording_id=recording_id,
                language=None,
                detected_languages="[]",
                status="processing",
                encryption_key_ref="env:AUDIO_ENCRYPTION_KEY",
            )
            db.add(transcript)
            await db.flush()
        else:
            transcript.status = "processing"

        existing_chunks = set((await db.execute(
            select(TranscriptSegment.chunk_index)
            .where(TranscriptSegment.transcript_id == transcript.id)
            .group_by(TranscriptSegment.chunk_index)
        )).scalars().all())
        detected = set(json.loads(transcript.detected_languages))
        for chunk in chunks:
            if chunk.index in existing_chunks:
                continue
            logger.info("stt_provider_request_started job_id=%d recording_id=%d chunk_index=%d "
                        "provider=%s model=%s content_type=audio/wav byte_length=%d",
                        job_id, recording_id, chunk.index, job.provider, provider.model,
                        len(chunk.audio))
            response: ProviderTranscript = await provider.transcribe(chunk.audio, "audio/wav")
            logger.info("stt_provider_response_received job_id=%d recording_id=%d chunk_index=%d "
                        "language=%s segment_count=%d model=%s", job_id, recording_id,
                        chunk.index, response.language, len(response.segments), response.model)
            language = response.language.strip().lower()
            configured_languages = _supported_languages()
            if not configured_languages:
                raise STTError("supported_language_set_not_configured",
                               "Configure STT_SUPPORTED_LANGUAGES before accepting transcripts",
                               retryable=False)
            if language not in configured_languages:
                raise STTError("unsupported_language", "Detected language is not enabled for this service",
                               retryable=False)
            detected.add(language)
            ordered_segments = sorted(response.segments, key=lambda segment: segment.start_seconds)
            chunk_duration_seconds = (chunk.end_ms - chunk.start_ms) / 1000
            for segment_index, segment in enumerate(ordered_segments):
                if (not segment.text.strip() or not math.isfinite(segment.start_seconds)
                        or not math.isfinite(segment.end_seconds)
                        or not math.isfinite(segment.confidence)
                        or segment.start_seconds < 0 or segment.end_seconds <= segment.start_seconds
                        or not 0.0 <= segment.confidence <= 1.0):
                    raise STTError("invalid_transcript_segment", "Speech-to-text returned invalid segment data",
                                   retryable=False)
                seg_start = max(0.0, min(segment.start_seconds, chunk_duration_seconds))
                seg_end = max(seg_start, min(segment.end_seconds, chunk_duration_seconds))
                if seg_end <= seg_start:
                    continue
                start_ms = chunk.start_ms + round(seg_start * 1000)
                end_ms = chunk.start_ms + round(seg_end * 1000)
                aad = f"pcma-transcript-{transcript.id}-{chunk.index}-{segment_index}".encode()
                encrypted_text = encrypt_bytes(segment.text.strip().encode("utf-8"), aad)
                db.add(TranscriptSegment(
                    transcript_id=transcript.id,
                    chunk_index=chunk.index,
                    segment_index=segment_index,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    text_ciphertext=encrypted_text,
                    confidence=segment.confidence,
                    low_confidence=segment.confidence < settings.stt_confidence_floor,
                ))
            if not ordered_segments:
                logger.info("stt_chunk_no_speech job_id=%d recording_id=%d chunk_index=%d",
                            job_id, recording_id, chunk.index)
            if response.model != provider.model:
                raise STTError("stt_model_mismatch", "Provider model changed during one transcription job",
                               retryable=False)
            transcript.language = transcript.language or language
            transcript.detected_languages = json.dumps(sorted(detected))
            transcript.updated_at = _now()
            job.lease_expires_at = _now() + timedelta(seconds=settings.stt_job_lease_seconds)
            await db.commit()

        segment_count = (await db.execute(select(func.count(TranscriptSegment.id)).where(
            TranscriptSegment.transcript_id == transcript.id
        ))).scalar_one()
        if segment_count == 0:
            raise STTError("stt_no_segments", "Speech-to-text returned no timestamped segments",
                           retryable=False)
        transcript.status = "complete"
        transcript.updated_at = _now()
        conversation = (await db.execute(select(Conversation).where(
            Conversation.recording_id == recording_id
        ).with_for_update())).scalar_one_or_none()
        if conversation is None:
            conversation = Conversation(
                user_id=recording.user_id,
                recording_id=recording.id,
                title="Conversation",
                occurred_at=recording.started_at or recording.created_at,
            )
            db.add(conversation)
            await db.flush()
        transcript.conversation_id = conversation.id
        diarization_job = (await db.execute(select(AIProcessingJob).where(
            AIProcessingJob.recording_id == recording_id,
            AIProcessingJob.stage == "diarization",
        ).with_for_update())).scalar_one_or_none()
        if diarization_job is None:
            db.add(AIProcessingJob(
                recording_id=recording_id,
                stage="diarization",
                status="queued",
                provider=settings.diarization_provider,
                model_used=settings.diarization_model or None,
                attempts=0,
                max_attempts=settings.diarization_max_attempts,
                available_at=_now(),
                created_at=_now(),
                updated_at=_now(),
            ))
        job.status = "complete"
        job.completed_at = _now()
        job.lease_expires_at = None
        job.last_error_code = None
        job.updated_at = _now()
        recording.state = "ready_for_review"
        recording.status = "ready_for_review"
        recording.updated_at = _now()
        _audit(db, recording.user_id, recording.id, "transcription.completed",
               provider=job.provider, model=job.model_used, segment_count=segment_count)
        await db.commit()
    except Exception as exc:
        await db.rollback()
        if isinstance(exc, STTError):
            error = exc
        elif isinstance(exc, AudioStorageNotConfigured):
            error = STTError("audio_storage_unavailable", "Encrypted recording audio is unavailable",
                             retryable=False)
        elif isinstance(exc, EncryptionKeyUnavailable):
            error = STTError("transcript_encryption_unavailable", "Transcript encryption is not configured",
                             retryable=False)
        elif isinstance(exc, InvalidTag):
            error = STTError("audio_decryption_failed", "Stored audio could not be decrypted",
                             retryable=False)
        elif isinstance(exc, (OSError, ValueError)):
            error = STTError("audio_processing_failed", "Audio could not be prepared for transcription",
                             retryable=False)
        else:
            error = STTError("transcription_internal_error", "Transcription could not be completed",
                             retryable=True)
        frames = traceback.extract_tb(exc.__traceback__)
        safe_trace = " <- ".join(
            f"{frame.filename}:{frame.lineno}:{frame.name}" for frame in frames
        )
        logger.error("transcription_exception job_id=%d recording_id=%d exception_type=%s "
                     "source_error_code=%s mapped_error_code=%s traceback_frames=%s",
                     job_id, recording_id, type(exc).__name__,
                     exc.code if isinstance(exc, STTError) else "untyped",
                     error.code, safe_trace)
        job = (await db.execute(select(AIProcessingJob).where(AIProcessingJob.id == job_id)
                                .with_for_update())).scalar_one()
        recording = (await db.execute(select(Recording).where(Recording.id == recording_id)
                                      .with_for_update())).scalar_one()
        transcript = (await db.execute(select(Transcript).where(
            Transcript.recording_id == recording_id
        ).with_for_update())).scalar_one_or_none()
        job.last_error_code = error.code
        job.lease_expires_at = None
        job.updated_at = _now()
        if error.retryable and job.attempts < job.max_attempts:
            wait_seconds = settings.stt_retry_base_seconds * (2 ** max(0, job.attempts - 1))
            job.status = "queued"
            job.available_at = _now() + timedelta(seconds=wait_seconds)
            event = "transcription.retry_scheduled"
        else:
            job.status = "failed"
            job.completed_at = _now()
            recording.state = "failed"
            recording.status = "failed"
            recording.updated_at = _now()
            event = "transcription.failed"
            if transcript is not None:
                count = (await db.execute(select(func.count(TranscriptSegment.id)).where(
                    TranscriptSegment.transcript_id == transcript.id
                ))).scalar_one()
                transcript.status = "partial" if count else "failed"
                transcript.updated_at = _now()
        _audit(db, recording.user_id, recording.id, event,
               provider=job.provider, model=job.model_used or "", error_code=error.code,
               attempt=job.attempts)
        await db.commit()
    return True


async def retry_transcription(
    db: AsyncSession,
    recording_id: int,
    user_id: int,
    *,
    require_error_code: str | None = None,
) -> AIProcessingJob:
    job = await get_job_for_owner(db, recording_id, user_id, lock=True)
    if job is None:
        raise RecordingError("transcription_not_found", "Transcription job not found", 404)
    if job.status != "failed":
        raise RecordingError("transcription_not_failed", "Only a failed transcription can be retried")
    if require_error_code is not None and job.last_error_code != require_error_code:
        raise RecordingError(
            "transcription_retry_ineligible",
            f"Job last error code is '{job.last_error_code}', expected '{require_error_code}'",
            400,
        )
    recording = (await db.execute(select(Recording).where(
        Recording.id == recording_id, Recording.user_id == user_id
    ).with_for_update())).scalar_one_or_none()
    if recording is None:
        raise RecordingError("recording_not_found", "Recording not found", 404)

    job.status = "queued"
    job.attempts = 0
    job.max_attempts = settings.stt_max_attempts
    job.available_at = _now()
    job.lease_expires_at = None
    job.completed_at = None
    job.last_error_code = None
    job.provider = settings.stt_provider
    job.updated_at = _now()

    recording.state = "processing"
    recording.status = "processing"
    recording.updated_at = _now()

    transcript = (await db.execute(select(Transcript).where(
        Transcript.recording_id == recording_id
    ))).scalar_one_or_none()
    if transcript is not None:
        transcript.status = "processing"
        transcript.updated_at = _now()

    _audit(db, user_id, recording_id, "transcription.user_retry_requested",
           provider=job.provider)
    await db.commit()
    await db.refresh(job)
    return job


async def get_transcription_status(db: AsyncSession, recording_id: int,
                                   user_id: int) -> AIProcessingJob | None:
    return await get_job_for_owner(db, recording_id, user_id)


async def get_transcript(db: AsyncSession, recording_id: int,
                         user_id: int) -> dict | None:
    transcript = await get_transcript_for_owner(db, recording_id, user_id)
    if transcript is None:
        return None
    output = []
    try:
        for segment in transcript.segments:
            aad = f"pcma-transcript-{transcript.id}-{segment.chunk_index}-{segment.segment_index}".encode()
            plaintext = decrypt_bytes(segment.text_ciphertext, aad).decode("utf-8")
            output.append({
                "id": segment.id,
                "start_ms": segment.start_ms,
                "end_ms": segment.end_ms,
                "text": plaintext,
                "confidence": segment.confidence,
                "low_confidence": segment.low_confidence,
                "speaker_id": segment.speaker_id,
                "speaker_uncertain": segment.speaker_uncertain,
            })
    except (EncryptionKeyUnavailable, InvalidTag, ValueError, UnicodeDecodeError) as exc:
        raise RecordingError("transcript_unavailable", "Transcript could not be decrypted", 503) from exc
    speakers = []
    if transcript.conversation_id is not None:
        speakers = list((await db.execute(select(Speaker).where(
            Speaker.conversation_id == transcript.conversation_id
        ).order_by(Speaker.id))).scalars().all())
    return {
        "id": transcript.id,
        "recording_id": transcript.recording_id,
        "language": transcript.language,
        "detected_languages": json.loads(transcript.detected_languages),
        "status": transcript.status,
        "conversation_id": transcript.conversation_id,
        "segments": sorted(output, key=lambda segment: (segment["start_ms"], segment["end_ms"])),
        "speakers": speakers,
        "created_at": transcript.created_at,
    }


async def correct_transcript_segment(
    db: AsyncSession,
    recording_id: int,
    segment_id: int,
    user_id: int,
    new_text: str,
    *,
    re_extract: bool = False,
) -> dict:
    # 1. Resolve recording or conversation ownership
    recording = (await db.execute(
        select(Recording).where(Recording.id == recording_id, Recording.user_id == user_id)
    )).scalar_one_or_none()

    conversation_id = None
    if recording is None:
        conv = (await db.execute(
            select(Conversation).where(Conversation.id == recording_id, Conversation.user_id == user_id)
        )).scalar_one_or_none()
        if conv:
            conversation_id = conv.id
            recording_id = conv.recording_id
            recording = (await db.execute(
                select(Recording).where(Recording.id == recording_id, Recording.user_id == user_id)
            )).scalar_one_or_none()

    if recording is None:
        raise RecordingError("recording_not_found", "Recording or conversation not found or access denied", 404)

    # 2. Find Transcript
    t_res = await db.execute(
        select(Transcript).where(Transcript.recording_id == recording_id)
    )
    transcript = t_res.scalar_one_or_none()
    if not transcript:
        raise RecordingError("transcript_not_found", "Transcript not found for this recording", 404)

    resolved_conv_id = transcript.conversation_id or conversation_id
    if not resolved_conv_id and recording:
        conv_res = await db.execute(
            select(Conversation.id).where(
                Conversation.recording_id == recording.id,
                Conversation.user_id == user_id,
            ).order_by(Conversation.id.desc())
        )
        resolved_conv_id = conv_res.scalars().first()

    # 3. Find TranscriptSegment
    s_res = await db.execute(
        select(TranscriptSegment).where(
            TranscriptSegment.id == segment_id,
            TranscriptSegment.transcript_id == transcript.id,
        )
    )
    segment = s_res.scalar_one_or_none()
    if not segment:
        s_res_idx = await db.execute(
            select(TranscriptSegment).where(
                TranscriptSegment.segment_index == segment_id,
                TranscriptSegment.transcript_id == transcript.id,
            )
        )
        segment = s_res_idx.scalar_one_or_none()
    if not segment:
        raise RecordingError("segment_not_found", f"Transcript segment #{segment_id} not found", 404)

    # 4. Decrypt current text
    aad = f"pcma-transcript-{transcript.id}-{segment.chunk_index}-{segment.segment_index}".encode()
    old_text = ""
    for candidate_aad in [aad, transcript.encryption_key_ref.encode("utf-8")]:
        try:
            old_text = decrypt_bytes(segment.text_ciphertext, candidate_aad).decode("utf-8")
            break
        except Exception:
            pass

    cleaned_new_text = new_text.strip()
    if not cleaned_new_text:
        raise RecordingError("invalid_text", "Segment text cannot be empty", 400)

    # 5. Save audit history if text changed
    if cleaned_new_text != old_text:
        segment.text_ciphertext = encrypt_bytes(cleaned_new_text.encode("utf-8"), aad)
        segment.confidence = 1.0
        segment.low_confidence = False

        history = TranscriptEditHistory(
            transcript_id=transcript.id,
            segment_id=segment.id,
            user_id=user_id,
            old_text=old_text,
            new_text=cleaned_new_text,
            created_at=datetime.now(timezone.utc),
        )
        db.add(history)

        _audit(
            db,
            user_id=user_id,
            recording_id=recording.id,
            event_type="transcript_segment_edited",
            segment_id=segment.id,
            old_text=old_text,
            new_text=cleaned_new_text,
            conversation_id=resolved_conv_id,
        )

    # 6. Re-extract and refresh MOM if explicitly requested
    if re_extract and resolved_conv_id:
        from app.services.extraction_service import run_extraction_for_conversation
        from app.services.mom_service import generate_mom_for_conversation

        await run_extraction_for_conversation(db, resolved_conv_id, user_id)
        await generate_mom_for_conversation(db, resolved_conv_id, user_id, refresh_draft=True)

    await db.commit()
    await db.refresh(segment)

    return {
        "id": segment.id,
        "start_ms": segment.start_ms,
        "end_ms": segment.end_ms,
        "text": cleaned_new_text,
        "confidence": segment.confidence,
        "low_confidence": segment.low_confidence,
        "speaker_id": segment.speaker_id,
        "speaker_uncertain": segment.speaker_uncertain,
    }


async def get_segment_edit_history(
    db: AsyncSession, recording_id: int, segment_id: int, user_id: int
) -> list[TranscriptEditHistory]:
    recording = (await db.execute(
        select(Recording).where(Recording.id == recording_id, Recording.user_id == user_id)
    )).scalar_one_or_none()

    if recording is None:
        conv = (await db.execute(
            select(Conversation).where(Conversation.id == recording_id, Conversation.user_id == user_id)
        )).scalar_one_or_none()
        if conv:
            recording = (await db.execute(
                select(Recording).where(Recording.id == conv.recording_id, Recording.user_id == user_id)
            )).scalar_one_or_none()

    if recording is None:
        raise RecordingError("recording_not_found", "Recording not found or access denied", 404)

    hist_res = await db.execute(
        select(TranscriptEditHistory)
        .where(TranscriptEditHistory.segment_id == segment_id, TranscriptEditHistory.user_id == user_id)
        .order_by(TranscriptEditHistory.created_at.desc())
    )
    return list(hist_res.scalars().all())
