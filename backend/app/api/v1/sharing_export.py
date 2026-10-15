from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.database.session import get_db
from app.models import User
from app.schemas.sharing_export import (
    MOMExportRequest,
    MOMExportResponse,
    MOMRecipientResponse,
    MOMShareRequest,
)
from app.services.sharing_export_service import (
    export_mom,
    get_mom_shares,
    revoke_mom_share,
    share_mom,
)

router = APIRouter(prefix="/moms", tags=["Sharing & Export"])


@router.post(
    "/{mom_id}/share",
    response_model=MOMRecipientResponse,
    status_code=status.HTTP_201_CREATED,
)
async def share_mom_endpoint(
    mom_id: int,
    request: MOMShareRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        recipient = await share_mom(
            db, mom_id, current_user.id, request.recipient_email.strip()
        )
        return MOMRecipientResponse.model_validate(recipient)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/{mom_id}/share/{recipient_id}", response_model=MOMRecipientResponse)
async def revoke_share_endpoint(
    mom_id: int,
    recipient_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        recipient = await revoke_mom_share(db, recipient_id, current_user.id)
        return MOMRecipientResponse.model_validate(recipient)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/{mom_id}/shares", response_model=list[MOMRecipientResponse])
async def list_shares_endpoint(
    mom_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        shares = await get_mom_shares(db, mom_id, current_user.id)
        return [MOMRecipientResponse.model_validate(s) for s in shares]
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{mom_id}/export", response_model=MOMExportResponse)
async def export_mom_endpoint(
    mom_id: int,
    request: MOMExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await export_mom(db, mom_id, current_user.id, request.format.lower())
        return MOMExportResponse(
            job_id=result["job_id"],
            mom_id=result["mom_id"],
            format=result["format"],
            content=result["content"],
            file_path=result["file_path"],
            created_at=result["created_at"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
