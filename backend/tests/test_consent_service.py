import pytest

from app.database.session import AsyncSessionLocal
from app.models import User
from app.services.consent_service import check_recording_consent
from app.services.profile_service import update_user_jurisdiction


@pytest.mark.asyncio
async def test_recording_allowed_without_jurisdiction():
    async with AsyncSessionLocal() as db:
        user = User(auth_id="test-consent-no-jurisdiction")

        db.add(user)
        await db.commit()
        await db.refresh(user)

        allowed, jurisdiction = await check_recording_consent(
            db=db,
            user_id=user.id,
        )

        assert allowed is True
        assert jurisdiction is None

        await db.delete(user)
        await db.commit()


@pytest.mark.asyncio
async def test_recording_allowed_with_jurisdiction():
    async with AsyncSessionLocal() as db:
        user = User(auth_id="test-consent-with-jurisdiction")

        db.add(user)
        await db.commit()
        await db.refresh(user)

        await update_user_jurisdiction(
            db=db,
            user_id=user.id,
            jurisdiction="IN",
        )

        allowed, jurisdiction = await check_recording_consent(
            db=db,
            user_id=user.id,
        )

        assert allowed is True
        assert jurisdiction == "IN"

        await db.delete(user)
        await db.commit()