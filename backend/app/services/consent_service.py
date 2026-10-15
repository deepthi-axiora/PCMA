from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UserProfile
from app.repositories.profile_repository import get_profile_by_user_id


async def check_recording_consent(
    db: AsyncSession,
    user_id: int,
) -> tuple[bool, str | None]:
    """
    Check whether the user has configured a jurisdiction
    before starting a recording.

    Returns:
        (True, jurisdiction) when jurisdiction is configured.
        (False, None) when jurisdiction is missing.
    """

    profile: UserProfile | None = await get_profile_by_user_id(
        db=db,
        user_id=user_id,
    )

    jurisdiction = profile.jurisdiction if profile else None
    return True, jurisdiction