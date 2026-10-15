from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.core.security import get_current_user
from app.models import User
from app.schemas.profile import ProfileResponse, ProfileUpdate
from app.services.profile_service import (
    get_or_create_profile,
    update_user_jurisdiction,
)


router = APIRouter(
    prefix="/profile",
    tags=["Profile"],
)


@router.get(
    "",
    response_model=ProfileResponse,
)
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_or_create_profile(
        db=db,
        user_id=current_user.id,
    )


@router.patch(
    "",
    response_model=ProfileResponse,
)
async def update_profile(
    data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await update_user_jurisdiction(
        db=db,
        user_id=current_user.id,
        jurisdiction=data.jurisdiction,
    )