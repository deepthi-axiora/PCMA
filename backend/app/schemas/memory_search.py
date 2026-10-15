from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class PersonCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    org_id: int | None = None


class PersonResponse(BaseModel):
    id: int
    name: str
    org_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class MergePeopleRequest(BaseModel):
    target_person_id: int
    source_person_ids: list[int]


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TopicCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class TopicResponse(BaseModel):
    id: int
    name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MergeTopicsRequest(BaseModel):
    target_topic_id: int
    source_topic_ids: list[int]


class SearchResultResponse(BaseModel):
    conversation_id: int
    title: str
    occurred_at: datetime
    project_id: int | None = None
    summary: str
    snippet: str


class PersonalMemoryResponse(BaseModel):
    id: int
    conversation_id: int | None = None
    entity_type: str
    entity_id: int | None = None
    fact_text: str
    provenance_json: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
