from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limiter import check_rate_limit
from app.core.security import get_current_user
from app.database.session import get_db
from app.models import User
from app.schemas.sync_hardening import (
    BatchSyncRequest,
    BatchSyncResponse,
    SyncStatusResponse,
)
from app.services.sync_hardening_service import get_sync_status, process_batch_sync

router = APIRouter(prefix="/sync", tags=["Synchronization & Reliability"])


@router.post(
    "",
    response_model=BatchSyncResponse,
    dependencies=[Depends(check_rate_limit)],
)
async def sync_batch_endpoint(
    request: BatchSyncRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        raw_items = [item.model_dump() for item in request.items]
        result = await process_batch_sync(db, current_user.id, raw_items)
        return BatchSyncResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch synchronization failed: {str(exc)}",
        )


@router.get("/status", response_model=SyncStatusResponse)
async def sync_status_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await get_sync_status(db, current_user.id)
    return SyncStatusResponse(**result)
