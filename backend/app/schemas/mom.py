from datetime import datetime
from pydantic import BaseModel, ConfigDict


class MOMSectionResponse(BaseModel):
    id: int
    section_type: str
    title: str
    content_json: str

    model_config = ConfigDict(from_attributes=True)


class MOMResponse(BaseModel):
    id: int
    conversation_id: int
    title: str
    summary: str
    status: str
    confidence: float
    is_uncertain: bool
    is_user_edited: bool
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None = None
    sections: list[MOMSectionResponse] = []

    model_config = ConfigDict(from_attributes=True)


class MOMEditRequest(BaseModel):
    title: str | None = None
    summary: str | None = None


class MOMApproveRequest(BaseModel):
    confirmed_review: bool = False


class MOMEditHistoryResponse(BaseModel):
    id: int
    mom_id: int
    edited_field: str
    old_value: str | None = None
    new_value: str | None = None
    edited_at: datetime

    model_config = ConfigDict(from_attributes=True)
