from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class MOMShareRequest(BaseModel):
    recipient_email: str = Field(..., min_length=3, max_length=255)


class MOMRecipientResponse(BaseModel):
    id: int
    mom_id: int
    recipient_email: str
    share_token: str
    permissions: str
    is_revoked: bool
    shared_at: datetime
    revoked_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class MOMExportRequest(BaseModel):
    format: str = Field(..., description="Export format: markdown, json, or pdf")


class MOMExportResponse(BaseModel):
    job_id: int
    mom_id: int
    format: str
    content: str
    file_path: str | None = None
    created_at: datetime
