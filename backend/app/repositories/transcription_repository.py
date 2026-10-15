from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AIProcessingJob, Recording, Transcript


async def create_transcription_job(db: AsyncSession, recording_id: int,
                                   provider: str, max_attempts: int) -> AIProcessingJob:
    now = datetime.now(timezone.utc)
    job = AIProcessingJob(
        recording_id=recording_id,
        stage="transcription",
        status="queued",
        provider=provider,
        attempts=0,
        max_attempts=max_attempts,
        available_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    await db.flush()
    return job


async def get_job_for_owner(db: AsyncSession, recording_id: int,
                            user_id: int, *, lock: bool = False,
                            stage: str = "transcription") -> AIProcessingJob | None:
    statement = (
        select(AIProcessingJob)
        .join(Recording, Recording.id == AIProcessingJob.recording_id)
        .where(AIProcessingJob.recording_id == recording_id,
               AIProcessingJob.stage == stage,
               Recording.user_id == user_id)
    )
    if lock:
        statement = statement.with_for_update(of=AIProcessingJob)
    result = await db.execute(statement)
    return result.scalar_one_or_none()


async def get_transcript_for_owner(db: AsyncSession, recording_id: int,
                                   user_id: int) -> Transcript | None:
    result = await db.execute(
        select(Transcript)
        .options(selectinload(Transcript.segments))
        .execution_options(populate_existing=True)
        .join(Recording, Recording.id == Transcript.recording_id)
        .where(Transcript.recording_id == recording_id, Recording.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def claim_next_transcription_job(db: AsyncSession, lease_seconds: int,
                                       stage: str = "transcription") -> AIProcessingJob | None:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(AIProcessingJob)
        .where(
            AIProcessingJob.stage == stage,
            or_(
                (AIProcessingJob.status == "queued") & (AIProcessingJob.available_at <= now),
                (AIProcessingJob.status == "running") & (AIProcessingJob.lease_expires_at <= now),
            ),
        )
        .order_by(AIProcessingJob.created_at, AIProcessingJob.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = result.scalar_one_or_none()
    if job is None:
        return None
    job.status = "running"
    job.attempts += 1
    job.started_at = now
    job.lease_expires_at = now + timedelta(seconds=lease_seconds)
    job.updated_at = now
    await db.flush()
    return job
