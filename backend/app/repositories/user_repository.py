from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


async def get_user_by_auth_id(
    db: AsyncSession,
    auth_id: str,
) -> User | None:
    result = await db.execute(
        select(User).where(User.auth_id == auth_id)
    )

    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    auth_id: str,
) -> User:
    user = User(auth_id=auth_id)

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user