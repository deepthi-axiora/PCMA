import pytest

from app.core.security import get_current_user
from app.database.session import AsyncSessionLocal
from app.models import User
from app.repositories.user_repository import get_user_by_auth_id


@pytest.mark.asyncio
async def test_get_current_user_creates_first_time_user():
    auth_id = "test-first-login-user"

    async with AsyncSessionLocal() as db:
        # Make sure this test starts with no existing user.
        existing_user = await get_user_by_auth_id(
            db=db,
            auth_id=auth_id,
        )

        if existing_user is not None:
            await db.delete(existing_user)
            await db.commit()

        # Simulate the payload returned from a valid Auth0 token.
        payload = {
            "sub": auth_id,
        }

        # First authenticated request should create the PCMA user.
        user = await get_current_user(
            payload=payload,
            db=db,
        )

        assert user is not None
        assert user.id is not None
        assert user.auth_id == auth_id

        # Confirm the user was actually persisted.
        saved_user = await get_user_by_auth_id(
            db=db,
            auth_id=auth_id,
        )

        assert saved_user is not None
        assert saved_user.id == user.id

        # Cleanup test data.
        await db.delete(saved_user)
        await db.commit()
@pytest.mark.asyncio
async def test_get_current_user_returns_existing_user():
    auth_id = "test-existing-user"

    async with AsyncSessionLocal() as db:
        test_user = User(auth_id=auth_id)

        db.add(test_user)
        await db.commit()
        await db.refresh(test_user)

        payload = {
            "sub": auth_id,
        }

        user = await get_current_user(
            payload=payload,
            db=db,
        )

        assert user is not None
        assert user.id == test_user.id
        assert user.auth_id == auth_id

        await db.delete(test_user)
        await db.commit()