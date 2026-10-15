from datetime import datetime
from pydantic import BaseModel, ConfigDict


class UserDataDeletionResponse(BaseModel):
    user_id: int
    status: str
    deleted_at: datetime


class UserDataExportResponse(BaseModel):
    user: dict
    conversations: list[dict]
    minutes_of_meeting: list[dict]
    commitments: list[dict]
    reminders: list[dict]
    exported_at: str


class AccountDeletionResponse(BaseModel):
    user_id: int
    status: str
    deleted_at: datetime


class HealthCheckResponse(BaseModel):
    status: str
    app_name: str
    app_version: str
    timestamp: datetime
