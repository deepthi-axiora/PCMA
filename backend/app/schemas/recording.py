from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RecordingStart(BaseModel):
    audio_source: str
    source_available: bool
    microphone_permission_granted: bool
    consent_acknowledged: bool


class AudioSourceChange(BaseModel):
    audio_source: str
    source_available: bool


class RecordingResponse(BaseModel):
    id: int
    user_id: int
    state: str | None
    audio_source: str | None
    started_at: datetime | None
    stopped_at: datetime | None
    duration_ms: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AudioFileResponse(BaseModel):
    id: int
    recording_id: int
    content_type: str
    size_bytes: int
    duration_ms: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
