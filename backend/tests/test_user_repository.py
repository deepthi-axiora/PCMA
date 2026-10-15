import pytest

from app.database.session import AsyncSessionLocal
from app.models import User
from app.repositories.user_repository import (
    create_user,
    get_user_by_auth_id,
)


@pytest.mark.asyncio
async def test_get_user_by_auth_id():
    async with AsyncSessionLocal() as db:
        test_user = User(auth_id="test-auth-user")

        db.add(test_user)
        await db.commit()
        await db.refresh(test_user)

        user = await get_user_by_auth_id(
            db=db,
            auth_id="test-auth-user",
        )

        assert user is not None
        assert user.id == test_user.id
        assert user.auth_id == "test-auth-user"

        await db.delete(test_user)
        await db.commit()


@pytest.mark.asyncio
async def test_create_user():
    async with AsyncSessionLocal() as db:
        user = await create_user(
            db=db,
            auth_id="test-created-user",
        )

        assert user.id is not None
        assert user.auth_id == "test-created-user"

        await db.delete(user)
        await db.commit()