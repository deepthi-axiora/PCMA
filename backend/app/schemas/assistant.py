from pydantic import BaseModel, Field


class AssistantQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000, description="User's query for the assistant")


class AssistantQueryResponse(BaseModel):
    query: str
    intent: str
    answer: str
    sources: list[dict]
    no_record_found: bool
