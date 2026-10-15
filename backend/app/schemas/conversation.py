from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.schemas.extraction import (
    ActionItemResponse,
    CommitmentResponse,
    DeadlineResponse,
    DecisionResponse,
    QuestionResponse,
    TopicResponse,
)
from app.schemas.memory_search import PersonResponse


class ConversationResponse(BaseModel):
    id: int
    recording_id: int | None = None
    user_id: int
    title: str = "Conversation"
    occurred_at: datetime | None = None
    created_at: datetime | None = None
    snippet: str | None = None
    status: str | None = None
    state: str | None = None
    topics: list[TopicResponse] = []
    action_items: list[ActionItemResponse] = []
    commitments: list[CommitmentResponse] = []
    decisions: list[DecisionResponse] = []
    deadlines: list[DeadlineResponse] = []
    questions: list[QuestionResponse] = []
    people: list[PersonResponse] = []
    organizations: list[TopicResponse] = []

    model_config = ConfigDict(from_attributes=True)
