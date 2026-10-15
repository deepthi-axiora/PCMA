from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.database.session import get_db
from app.models import User
from app.schemas.memory_search import (
    MergePeopleRequest,
    MergeTopicsRequest,
    PersonalMemoryResponse,
    PersonCreate,
    PersonResponse,
    ProjectCreate,
    ProjectResponse,
    SearchResultResponse,
    TopicCreate,
    TopicResponse,
)
from app.services.memory_search_service import (
    create_person,
    create_project,
    create_topic,
    get_people,
    get_personal_memories,
    get_projects,
    get_topics,
    merge_people,
    merge_topics,
    search_conversations,
)

router = APIRouter(tags=["Memory, Graph & Search"])


# --- PEOPLE ---
@router.post("/people", response_model=PersonResponse, status_code=status.HTTP_201_CREATED)
async def create_person_endpoint(
    request: PersonCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    person = await create_person(db, current_user.id, request.name, request.org_id)
    return PersonResponse.model_validate(person)


@router.get("/people", response_model=list[PersonResponse])
async def list_people_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    people = await get_people(db, current_user.id)
    return [PersonResponse.model_validate(p) for p in people]


@router.post("/people/merge", response_model=PersonResponse)
async def merge_people_endpoint(
    request: MergePeopleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        person = await merge_people(
            db, current_user.id, request.target_person_id, request.source_person_ids
        )
        return PersonResponse.model_validate(person)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# --- PROJECTS ---
@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project_endpoint(
    request: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    proj = await create_project(db, current_user.id, request.name, request.description)
    return ProjectResponse.model_validate(proj)


@router.get("/projects", response_model=list[ProjectResponse])
async def list_projects_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    projects = await get_projects(db, current_user.id)
    return [ProjectResponse.model_validate(p) for p in projects]


# --- TOPICS ---
@router.post("/topics", response_model=TopicResponse, status_code=status.HTTP_201_CREATED)
async def create_topic_endpoint(
    request: TopicCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    topic = await create_topic(db, current_user.id, request.name)
    return TopicResponse.model_validate(topic)


@router.get("/topics", response_model=list[TopicResponse])
async def list_topics_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    topics = await get_topics(db, current_user.id)
    return [TopicResponse.model_validate(t) for t in topics]


@router.post("/topics/merge", response_model=TopicResponse)
async def merge_topics_endpoint(
    request: MergeTopicsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        topic = await merge_topics(
            db, current_user.id, request.target_topic_id, request.source_topic_ids
        )
        return TopicResponse.model_validate(topic)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# --- SEARCH ---
@router.get("/search", response_model=list[SearchResultResponse])
async def search_endpoint(
    query: str | None = Query(default=None),
    person_id: int | None = Query(default=None),
    project_id: int | None = Query(default=None),
    topic_id: int | None = Query(default=None),
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    results = await search_conversations(
        db,
        current_user.id,
        query=query,
        person_id=person_id,
        project_id=project_id,
        topic_id=topic_id,
        start_date=start_date,
        end_date=end_date,
    )
    return [SearchResultResponse(**r) for r in results]


# --- MEMORY ---
@router.get("/memory", response_model=list[PersonalMemoryResponse])
async def memory_recall_endpoint(
    entity_type: str | None = Query(default=None),
    entity_id: int | None = Query(default=None),
    query: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    memories = await get_personal_memories(
        db, current_user.id, entity_type=entity_type, entity_id=entity_id, query=query
    )
    return [PersonalMemoryResponse.model_validate(m) for m in memories]
