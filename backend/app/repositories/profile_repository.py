from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UserProfile


async def get_profile_by_user_id(
    db: AsyncSession,
    user_id: int,
) -> UserProfile | None:
    result = await db.execute(
        select(UserProfile).where(
            UserProfile.user_id == user_id
        )
    )

    return result.scalar_one_or_none()


async def create_profile(
    db: AsyncSession,
    user_id: int,
    jurisdiction: str | None = None,
) -> UserProfile:
    profile = UserProfile(
        user_id=user_id,
        jurisdiction=jurisdiction,
    )

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    return profile


async def update_profile_jurisdiction(
    db: AsyncSession,
    profile: UserProfile,
    jurisdiction: str,
) -> UserProfile:
    profile.jurisdiction = jurisdiction

    await db.commit()
    await db.refresh(profile)

    return profile