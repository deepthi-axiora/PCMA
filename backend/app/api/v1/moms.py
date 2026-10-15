from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.database.session import get_db
from app.models import User
from app.schemas.mom import (
    MOMApproveRequest,
    MOMEditHistoryResponse,
    MOMEditRequest,
    MOMResponse,
)
from app.services.mom_service import (
    approve_mom,
    edit_mom,
    generate_mom_for_conversation,
    get_mom_by_conversation,
    get_mom_edit_history,
)

router = APIRouter(tags=["Minutes of Meeting (MOM)"])


@router.post(
    "/conversations/{conversation_id}/mom/generate",
    response_model=MOMResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_mom(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        mom = await generate_mom_for_conversation(db, conversation_id, current_user.id)
        return MOMResponse.model_validate(mom)
    except ValueError as exc:
        err_msg = str(exc)
        if "extraction_not_ready" in err_msg:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)


@router.get("/conversations/{conversation_id}/mom", response_model=MOMResponse)
async def get_mom(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        mom = await get_mom_by_conversation(db, conversation_id, current_user.id)
        if not mom:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="MOM not found"
            )
        return MOMResponse.model_validate(mom)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.patch("/moms/{mom_id}", response_model=MOMResponse)
async def update_mom(
    mom_id: int,
    request: MOMEditRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        mom = await edit_mom(
            db,
            mom_id,
            current_user.id,
            title=request.title,
            summary=request.summary,
        )
        return MOMResponse.model_validate(mom)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/moms/{mom_id}/approve", response_model=MOMResponse)
async def approve_mom_endpoint(
    mom_id: int,
    request: MOMApproveRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        confirmed = request.confirmed_review if request else False
        mom = await approve_mom(db, mom_id, current_user.id, confirmed_review=confirmed)
        return MOMResponse.model_validate(mom)
    except ValueError as exc:
        err_msg = str(exc)
        if "human_review_required" in err_msg:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)


@router.get("/moms/{mom_id}/history", response_model=list[MOMEditHistoryResponse])
async def get_history(
    mom_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        history = await get_mom_edit_history(db, mom_id, current_user.id)
        return [MOMEditHistoryResponse.model_validate(h) for h in history]
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
