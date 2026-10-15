import json
import logging
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import (AIProcessingJob, AudioFile, AuditEvent, Conversation, Recording,
                        Speaker, Transcript, TranscriptSegment)
from app.repositories.transcription_repository import claim_next_transcription_job, get_job_for_owner
from app.services.audio_storage import read_encrypted_audio
from app.services.encryption import decrypt_bytes
from app.services.diarization_provider import (
    DiarizationError, DiarizationInputSegment, DiarizationProvider,
    create_diarization_provider,
)
from app.services.recording_service import RecordingError

logger = logging.getLogger("pcma.diarization_service")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _audit(db: AsyncSession, user_id: int, speaker_id: int | None,
           event_type: str, metadata: dict) -> None:
    db.add(AuditEvent(user_id=user_id, event_type=event_type, entity_type="Speaker",
                      entity_id=speaker_id, metadata_json=json.dumps(metadata, separators=(",", ":"))))


async def process_next_diarization_job(db: AsyncSession,
                                      provider: DiarizationProvider | None = None) -> bool:
    job = await claim_next_transcription_job(db, settings.stt_job_lease_seconds, stage="diarization")
    if job is None:
        await db.rollback()
        return False
    job_id, recording_id = job.id, job.recording_id
    await db.commit()
    try:
        job = (await db.execute(select(AIProcessingJob).where(AIProcessingJob.id == job_id)
                                .with_for_update())).scalar_one()
        recording = (await db.execute(select(Recording).where(Recording.id == recording_id)
                                      .with_for_update())).scalar_one()
        conversation = (await db.execute(select(Conversation).where(
            Conversation.recording_id == recording_id,
            Conversation.user_id == recording.user_id,
        ).with_for_update())).scalar_one_or_none()
        transcript = (await db.execute(select(Transcript).where(
            Transcript.recording_id == recording_id
        ).with_for_update())).scalar_one_or_none()
        if conversation is None or transcript is None or transcript.status != "complete":
            raise DiarizationError("diarization_transcript_not_ready",
                                   "A completed transcript is required for speaker diarization",
                                   retryable=True)
        segments = (await db.execute(select(TranscriptSegment).where(
            TranscriptSegment.transcript_id == transcript.id
        ).order_by(TranscriptSegment.start_ms, TranscriptSegment.id).with_for_update())).scalars().all()
        if not segments:
            raise DiarizationError("diarization_segments_missing", "Transcript segments are unavailable",
                                   retryable=False)
        audio_file = (await db.execute(select(AudioFile).where(
            AudioFile.recording_id == recording_id
        ))).scalar_one_or_none()
        if audio_file is None:
            raise DiarizationError("diarization_audio_missing", "Recording audio is unavailable",
                                   retryable=False)
        if provider is None:
            provider = create_diarization_provider(settings.diarization_provider if (job.provider == "http_json" and not settings.diarization_api_base_url) else job.provider, job.model_used)
        job.provider = provider.name
        job.model_used = provider.model
        audio = read_encrypted_audio(audio_file.storage_ref)
        input_segments = []
        for segment in segments:
            aad = f"pcma-transcript-{transcript.id}-{segment.chunk_index}-{segment.segment_index}".encode()
            text = decrypt_bytes(segment.text_ciphertext, aad).decode("utf-8")
            input_segments.append(DiarizationInputSegment(segment.id, segment.start_ms,
                                                          segment.end_ms, text))
        _audit(db, recording.user_id, None, "diarization.started",
               {"provider": job.provider, "attempt": job.attempts})
        await db.commit()
        assignments = await provider.diarize(audio, audio_file.content_type, input_segments)
        by_segment: dict[int, object] = {}
        expected_ids = {item.id for item in input_segments}
        for assignment in assignments:
            if assignment.segment_id not in expected_ids or assignment.segment_id in by_segment:
                raise DiarizationError("diarization_invalid_response",
                                       "Diarization returned invalid segment assignments", retryable=False)
            if (not assignment.speaker_label or not math.isfinite(assignment.confidence)
                    or not 0 <= assignment.confidence <= 1):
                raise DiarizationError("diarization_invalid_response",
                                       "Diarization returned invalid speaker confidence", retryable=False)
            by_segment[assignment.segment_id] = assignment

        confident = [by_segment.get(segment.id) for segment in segments]
        is_single_speaker = bool(confident) and all(
            item is not None and item.confidence >= settings.diarization_confidence_floor
            for item in confident
        ) and len({item.speaker_label for item in confident}) == 1
        uncertain_speaker = None
        speaker_by_label: dict[str, Speaker] = {}
        if is_single_speaker:
            user_speaker = Speaker(conversation_id=conversation.id, label="You", is_user=True,
                                   confirmed=False, uncertain=False,
                                   confidence=min(item.confidence for item in confident))
            db.add(user_speaker)
            await db.flush()
            for segment in segments:
                segment.speaker_id = user_speaker.id
                segment.speaker_uncertain = False
        else:
            for segment in segments:
                assignment = by_segment.get(segment.id)
                if assignment is None or assignment.confidence < settings.diarization_confidence_floor:
                    if uncertain_speaker is None:
                        uncertain_speaker = Speaker(conversation_id=conversation.id,
                                                    label="Uncertain speaker", uncertain=True,
                                                    is_user=False, confirmed=False,
                                                    confidence=assignment.confidence if assignment else None)
                        db.add(uncertain_speaker)
                        await db.flush()
                    segment.speaker_id = uncertain_speaker.id
                    segment.speaker_uncertain = True
                    continue
                speaker = speaker_by_label.get(assignment.speaker_label)
                if speaker is None:
                    speaker = Speaker(conversation_id=conversation.id,
                                      label=f"Speaker {len(speaker_by_label) + 1}",
                                      uncertain=False, is_user=False, confirmed=False,
                                      confidence=assignment.confidence)
                    db.add(speaker)
                    await db.flush()
                    speaker_by_label[assignment.speaker_label] = speaker
                segment.speaker_id = speaker.id
                segment.speaker_uncertain = False
        job.status = "complete"
        job.completed_at = _now()
        job.lease_expires_at = None
        job.last_error_code = None
        job.updated_at = _now()
        ext_job = (await db.execute(select(AIProcessingJob).where(
            AIProcessingJob.recording_id == recording_id,
            AIProcessingJob.stage == "structured_extraction",
        ).with_for_update())).scalar_one_or_none()
        if ext_job is None:
            db.add(AIProcessingJob(
                recording_id=recording_id,
                stage="structured_extraction",
                status="queued",
                provider=settings.llm_provider,
                model_used=settings.llm_model,
                attempts=0,
                max_attempts=3,
                available_at=_now(),
                created_at=_now(),
                updated_at=_now(),
            ))
        _audit(db, recording.user_id, None, "diarization.completed",
               {"provider": job.provider, "speaker_count": len(speaker_by_label) + int(is_single_speaker)})
        await db.commit()
    except Exception as exc:
        await db.rollback()
        if isinstance(exc, DiarizationError):
            error = exc
        else:
            # Do not expose audio, transcript text, provider payloads, or credentials.
            logger.error("diarization_unexpected_error job_id=%d recording_id=%d type=%s",
                         job_id, recording_id, type(exc).__name__)
            error = DiarizationError("diarization_processing_failed",
                                     "Speaker diarization could not be completed", retryable=False)
        job = (await db.execute(select(AIProcessingJob).where(AIProcessingJob.id == job_id)
                                .with_for_update())).scalar_one()
        recording = (await db.execute(select(Recording).where(Recording.id == recording_id)
                                      .with_for_update())).scalar_one()
        job.last_error_code = error.code
        job.lease_expires_at = None
        job.updated_at = _now()
        if error.retryable and job.attempts < job.max_attempts:
            delay = settings.stt_retry_base_seconds * (2 ** max(0, job.attempts - 1))
            job.status = "queued"
            job.available_at = _now() + timedelta(seconds=delay)
            event = "diarization.retry_scheduled"
        else:
            job.status = "failed"
            job.completed_at = _now()
            event = "diarization.failed"
            # Pipeline continuity: Even if speaker diarization fails or is unavailable,
            # downstream structured extraction must still run on transcript text!
            ext_job = (await db.execute(select(AIProcessingJob).where(
                AIProcessingJob.recording_id == recording_id,
                AIProcessingJob.stage == "structured_extraction",
            ).with_for_update())).scalar_one_or_none()
            if ext_job is None:
                db.add(AIProcessingJob(
                    recording_id=recording_id,
                    stage="structured_extraction",
                    status="queued",
                    provider=settings.llm_provider,
                    model_used=settings.llm_model,
                    attempts=0,
                    max_attempts=3,
                    available_at=_now(),
                    created_at=_now(),
                    updated_at=_now(),
                ))
        _audit(db, recording.user_id, None, event,
               {"provider": job.provider, "error_code": error.code, "attempt": job.attempts})
        await db.commit()
    return True


async def get_diarization_status(db: AsyncSession, recording_id: int, user_id: int):
    return await get_job_for_owner(db, recording_id, user_id, stage="diarization")


async def relabel_speaker(db: AsyncSession, recording_id: int, speaker_id: int, user_id: int,
                          label: str | None, person_id: int | None = None,
                          *, replace_person: bool = True) -> Speaker:
    from sqlalchemy import or_
    label = label.strip() if label is not None else None
    if label == "":
        raise RecordingError("invalid_speaker_label", "Speaker label cannot be empty", 422)
    if label is None and person_id is None and not replace_person:
        raise RecordingError("invalid_speaker_update", "Provide a label or person mapping", 422)

    # Find conversation by recording_id or id
    conv_res = await db.execute(select(Conversation).where(
        or_(Conversation.recording_id == recording_id, Conversation.id == recording_id),
        Conversation.user_id == user_id,
    ))
    conversation = conv_res.scalar_one_or_none()
    if not conversation:
        raise RecordingError("conversation_not_found", "Conversation not found", 404)

    speaker = None
    if speaker_id > 0:
        speaker = (await db.execute(select(Speaker).where(
            Speaker.id == speaker_id,
            Speaker.conversation_id == conversation.id,
        ).with_for_update())).scalar_one_or_none()

    if speaker is None:
        # Create speaker record and associate with unassigned transcript segments
        speaker = Speaker(
            conversation_id=conversation.id,
            label=label or "Speaker 1",
            uncertain=False,
            is_user=False,
            confirmed=True,
            confidence=1.0,
        )
        db.add(speaker)
        await db.flush()

        from app.models.transcription import Transcript, TranscriptSegment
        tr_res = await db.execute(select(Transcript).where(
            or_(Transcript.conversation_id == conversation.id, Transcript.recording_id == recording_id)
        ))
        tr = tr_res.scalar_one_or_none()
        if tr:
            seg_res = await db.execute(select(TranscriptSegment).where(
                TranscriptSegment.transcript_id == tr.id,
                TranscriptSegment.speaker_id == None,
            ))
            for s in seg_res.scalars().all():
                s.speaker_id = speaker.id

    if person_id is not None:
        from app.models import Person
        person = (await db.execute(select(Person).where(
            Person.id == person_id, Person.user_id == user_id
        ))).scalar_one_or_none()
        if person is None:
            raise RecordingError("person_not_found", "Person not found", 404)
        if replace_person:
            speaker.person_id = person_id
        speaker.label = person.name
    elif label is not None:
        speaker.label = label

    speaker.confirmed = True
    _audit(db, user_id, speaker.id, "speaker.relabeled", {"person_id": person_id or 0, "label": speaker.label})
    await db.commit()
    await db.refresh(speaker)
    return speaker
