import pytest

from app.database.session import AsyncSessionLocal
from app.models import User
from uuid import uuid4
from app.services.profile_service import (
    get_or_create_profile,
    update_user_jurisdiction,
)


@pytest.mark.asyncio
async def test_profile_jurisdiction():
    async with AsyncSessionLocal() as db:
        user = User(auth_id=f"test-profile-user-{uuid4()}")

        db.add(user)
        await db.commit()
        await db.refresh(user)

        # Profile should be created automatically.
        profile = await get_or_create_profile(
            db=db,
            user_id=user.id,
        )

        assert profile is not None
        assert profile.user_id == user.id
        assert profile.jurisdiction is None

        # User sets jurisdiction.
        updated_profile = await update_user_jurisdiction(
            db=db,
            user_id=user.id,
            jurisdiction="IN",
        )

        assert updated_profile.jurisdiction == "IN"

        # Verify it persists.
        profile_again = await get_or_create_profile(
            db=db,
            user_id=user.id,
        )

        assert profile_again.jurisdiction == "IN"

        # Cleanup.
        await db.delete(profile_again)
        await db.commit()