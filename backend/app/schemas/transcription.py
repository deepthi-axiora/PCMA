from datetime import datetime

from pydantic import BaseModel, ConfigDict
from pydantic import Field


class SpeakerResponse(BaseModel):
    id: int
    label: str
    person_id: int | None
    confidence: float | None
    uncertain: bool
    is_user: bool
    confirmed: bool

    model_config = ConfigDict(from_attributes=True)


class SpeakerRelabelRequest(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=120)
    person_id: int | None = None


class TranscriptSegmentResponse(BaseModel):
    id: int | None = None
    start_ms: int
    end_ms: int
    text: str
    confidence: float
    low_confidence: bool
    speaker_id: int | None = None
    speaker_uncertain: bool = False


class TranscriptSegmentCorrectionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    re_extract: bool = False


class TranscriptEditHistoryResponse(BaseModel):
    id: int
    transcript_id: int
    segment_id: int
    user_id: int
    old_text: str
    new_text: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)



class TranscriptResponse(BaseModel):
    id: int
    recording_id: int
    language: str | None
    detected_languages: list[str]
    status: str
    conversation_id: int | None = None
    segments: list[TranscriptSegmentResponse]
    speakers: list[SpeakerResponse] = Field(default_factory=list)
    created_at: datetime


class TranscriptionStatusResponse(BaseModel):
    id: int
    recording_id: int
    stage: str
    status: str
    provider: str
    model_used: str | None
    attempts: int
    max_attempts: int
    last_error_code: str | None
    last_error_message: str | None = None
    available_at: datetime

    model_config = ConfigDict(from_attributes=True)
