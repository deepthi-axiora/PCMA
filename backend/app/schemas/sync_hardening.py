from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class SyncItemRequest(BaseModel):
    action: str = Field(..., description="Action name: update_commitment_status, log_offline_event")
    payload: dict = Field(default_factory=dict)
    timestamp: datetime | None = None


class BatchSyncRequest(BaseModel):
    items: list[SyncItemRequest] = Field(default_factory=list)


class BatchSyncResponse(BaseModel):
    user_id: int
    processed_count: int
    failed_count: int
    errors: list[dict] = []
    synced_at: datetime


class SyncStatusResponse(BaseModel):
    user_id: int
    open_recordings_count: int
    last_synced_at: datetime
    status: str
