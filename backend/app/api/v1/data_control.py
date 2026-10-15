from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.database.session import get_db
from app.models import User
from app.schemas.data_control import (
    AccountDeletionResponse,
    UserDataDeletionResponse,
    UserDataExportResponse,
)
from app.services.data_control_service import (
    delete_user_account,
    delete_user_data,
    export_user_data_package,
)

router = APIRouter(prefix="/me", tags=["Data Control & Privacy (FR-42, FR-43, FR-44)"])


@router.delete("/data", response_model=UserDataDeletionResponse)
async def delete_user_data_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await delete_user_data(db, current_user.id)
        return UserDataDeletionResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Data deletion failed: {str(exc)}",
        )


@router.post("/export", response_model=UserDataExportResponse)
async def export_user_data_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await export_user_data_package(db, current_user.id)
        return UserDataExportResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Data export failed: {str(exc)}",
        )


@router.delete("/account", response_model=AccountDeletionResponse)
async def delete_account_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await delete_user_account(db, current_user.id)
        return AccountDeletionResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Account deletion failed: {str(exc)}",
        )
