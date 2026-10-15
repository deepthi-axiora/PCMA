from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.repositories.user_repository import (
    create_user,
    get_user_by_auth_id,
)


async def find_user_by_auth_id(
    db: AsyncSession,
    auth_id: str,
) -> User | None:
    return await get_user_by_auth_id(
        db=db,
        auth_id=auth_id,
    )


async def create_user_for_auth(
    db: AsyncSession,
    auth_id: str,
) -> User:
    return await create_user(
        db=db,
        auth_id=auth_id,
    )