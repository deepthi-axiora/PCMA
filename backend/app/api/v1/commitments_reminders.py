from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.database.session import get_db
from app.models import User
from app.schemas.commitments_reminders import (
    ActionItemStatusUpdateRequest,
    CommitmentStatusUpdateRequest,
    ReminderCreate,
    ReminderResponse,
)
from app.schemas.extraction import ActionItemResponse, CommitmentResponse
from app.services.commitment_reminder_service import (
    cancel_reminder,
    create_reminder,
    get_user_action_items,
    get_user_commitments,
    get_user_reminders,
    update_action_item_status,
    update_commitment_status,
)

router = APIRouter(tags=["Commitments & Reminders"])


@router.get("/commitments", response_model=list[CommitmentResponse])
async def list_commitments_endpoint(
    status: str | None = Query(default=None, description="Filter: open, due, overdue, due-tomorrow, fulfilled"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    commitments = await get_user_commitments(db, current_user.id, status_filter=status)
    return [CommitmentResponse(**c) for c in commitments]


@router.patch("/commitments/{commitment_id}", response_model=CommitmentResponse)
async def update_commitment_endpoint(
    commitment_id: int,
    request: CommitmentStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        c = await update_commitment_status(
            db, commitment_id, current_user.id, request.status
        )
        return CommitmentResponse.model_validate(c)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/action-items", response_model=list[ActionItemResponse])
async def list_action_items_endpoint(
    status: str | None = Query(default=None, description="Filter: open, due, overdue, due-tomorrow, completed"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    items = await get_user_action_items(db, current_user.id, status_filter=status)
    return [ActionItemResponse(**a) for a in items]


@router.patch("/action-items/{action_item_id}", response_model=ActionItemResponse)
async def update_action_item_endpoint(
    action_item_id: int,
    request: ActionItemStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        a = await update_action_item_status(
            db, action_item_id, current_user.id, request.status
        )
        return ActionItemResponse.model_validate(a)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/reminders", response_model=list[ReminderResponse])
async def list_reminders_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    reminders = await get_user_reminders(db, current_user.id)
    return [ReminderResponse.model_validate(r) for r in reminders]


@router.post("/reminders", response_model=ReminderResponse, status_code=status.HTTP_201_CREATED)
async def create_reminder_endpoint(
    request: ReminderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    reminder = await create_reminder(
        db,
        current_user.id,
        title=request.title,
        remind_at=request.remind_at,
        user_timezone=request.timezone,
        commitment_id=request.commitment_id,
        action_item_id=request.action_item_id,
        deadline_id=request.deadline_id,
        priority=request.priority,
    )
    return ReminderResponse.model_validate(reminder)


@router.patch("/reminders/{reminder_id}/cancel", response_model=ReminderResponse)
async def cancel_reminder_endpoint(
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        reminder = await cancel_reminder(db, reminder_id, current_user.id)
        return ReminderResponse.model_validate(reminder)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
