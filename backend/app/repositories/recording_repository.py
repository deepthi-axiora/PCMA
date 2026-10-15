from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Recording


async def create_recording(
    db: AsyncSession,
    user_id: int,
) -> Recording:
    recording = Recording(
        user_id=user_id,
        status="created",
    )

    db.add(recording)
    await db.commit()
    await db.refresh(recording)

    return recording


async def get_recording_by_id(
    db: AsyncSession,
    recording_id: int,
    user_id: int,
) -> Recording | None:
    result = await db.execute(
        select(Recording).where(
            Recording.id == recording_id,
            Recording.user_id == user_id,
        )
    )

    return result.scalar_one_or_none()


async def update_recording_status(
    db: AsyncSession,
    recording: Recording,
    status: str,
) -> Recording:
    recording.status = status

    await db.commit()
    await db.refresh(recording)

    return recording