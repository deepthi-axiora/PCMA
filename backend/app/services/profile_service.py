from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UserProfile
from app.repositories.profile_repository import (
    create_profile,
    get_profile_by_user_id,
    update_profile_jurisdiction,
)


async def get_or_create_profile(
    db: AsyncSession,
    user_id: int,
) -> UserProfile:
    profile = await get_profile_by_user_id(
        db=db,
        user_id=user_id,
    )

    if profile is None:
        profile = await create_profile(
            db=db,
            user_id=user_id,
        )

    return profile


async def update_user_jurisdiction(
    db: AsyncSession,
    user_id: int,
    jurisdiction: str,
) -> UserProfile:
    profile = await get_or_create_profile(
        db=db,
        user_id=user_id,
    )

    return await update_profile_jurisdiction(
        db=db,
        profile=profile,
        jurisdiction=jurisdiction,
    )