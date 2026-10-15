from datetime import datetime
from pydantic import BaseModel, ConfigDict


class TopicResponse(BaseModel):
    id: int
    name: str
    confidence: float = 1.0
    is_uncertain: bool = False
    source_segment_ids: list[int] = []

    model_config = ConfigDict(from_attributes=True)


class DecisionResponse(BaseModel):
    id: int
    conversation_id: int
    text: str
    confidence: float
    is_uncertain: bool
    source_segment_ids: list[int] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActionItemResponse(BaseModel):
    id: int
    conversation_id: int
    assignee_id: int | None = None
    assignee_name: str | None = None
    text: str
    due_date: datetime | None = None
    status: str
    confidence: float
    is_uncertain: bool
    source_segment_ids: list[int] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommitmentResponse(BaseModel):
    id: int
    conversation_id: int
    promiser_id: int | None = None
    promiser_name: str | None = None
    promisee_id: int | None = None
    promisee_name: str | None = None
    text: str
    due_date: datetime | None = None
    status: str
    confidence: float
    is_uncertain: bool
    source_segment_ids: list[int] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeadlineResponse(BaseModel):
    id: int
    conversation_id: int
    title: str
    due_date: datetime | None = None
    raw_deadline_text: str | None = None
    status: str
    confidence: float
    is_uncertain: bool
    source_segment_ids: list[int] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QuestionResponse(BaseModel):
    id: int
    conversation_id: int
    question_text: str
    asker_name: str | None = None
    answer_text: str | None = None
    status: str
    confidence: float
    is_uncertain: bool
    source_segment_ids: list[int] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AIExtractionResponse(BaseModel):
    id: int
    conversation_id: int
    stage: str
    status: str
    model_used: str | None = None
    provider: str | None = None
    prompt_tokens: int
    completion_tokens: int
    estimated_cost: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationExtractionsResponse(BaseModel):
    conversation_id: int
    topics: list[TopicResponse]
    decisions: list[DecisionResponse]
    action_items: list[ActionItemResponse]
    commitments: list[CommitmentResponse]
    deadlines: list[DeadlineResponse]
    questions: list[QuestionResponse]
    extraction: AIExtractionResponse | None = None
