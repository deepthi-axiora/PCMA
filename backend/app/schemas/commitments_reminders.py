from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class CommitmentStatusUpdateRequest(BaseModel):
    status: str = Field(..., description="Status: open, fulfilled, cancelled, overdue")


class ActionItemStatusUpdateRequest(BaseModel):
    status: str = Field(..., description="Status: open, completed, cancelled, in_progress")


class ReminderCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    remind_at: datetime
    timezone: str = "UTC"
    commitment_id: int | None = None
    action_item_id: int | None = None
    deadline_id: int | None = None
    priority: str = "normal"


class ReminderResponse(BaseModel):
    id: int
    title: str
    remind_at: datetime
    timezone: str
    status: str
    priority: str
    commitment_id: int | None = None
    action_item_id: int | None = None
    deadline_id: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
