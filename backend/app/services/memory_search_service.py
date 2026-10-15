import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Person, Speaker
from app.models.extraction import (
    ActionItem,
    Commitment,
    ConversationTopic,
    Deadline,
    Decision,
    Organization,
    Question,
    Topic,
)
from app.models.memory_search import PersonalMemory, Project
from app.models.mom import MOM
from app.models.recording import AuditEvent
from app.models.transcription import Transcript, TranscriptSegment
from app.services.encryption import decrypt_bytes

logger = logging.getLogger("pcma.memory_search_service")


# --- PEOPLE MANAGEMENT (FR-29) ---
async def create_person(db: AsyncSession, user_id: int, name: str, org_id: int | None = None) -> Person:
    person = Person(user_id=user_id, name=name.strip(), org_id=org_id)
    db.add(person)
    await db.commit()
    await db.refresh(person)
    return person


async def get_people(db: AsyncSession, user_id: int) -> list[Person]:
    res = await db.execute(select(Person).where(Person.user_id == user_id).order_by(Person.name))
    return list(res.scalars().all())


async def merge_people(
    db: AsyncSession, user_id: int, target_person_id: int, source_person_ids: list[int]
) -> Person:
    # Verify target person
    t_res = await db.execute(
        select(Person).where(Person.id == target_person_id, Person.user_id == user_id)
    )
    target_person = t_res.scalar_one_or_none()
    if not target_person:
        raise ValueError("Target person not found or access denied")

    # Reassign speakers
    await db.execute(
        update(Speaker)
        .where(Speaker.person_id.in_(source_person_ids))
        .values(person_id=target_person_id)
    )

    # Reassign action items
    await db.execute(
        update(ActionItem)
        .where(ActionItem.assignee_id.in_(source_person_ids), ActionItem.user_id == user_id)
        .values(assignee_id=target_person_id, assignee_name=target_person.name)
    )

    # Reassign commitments
    await db.execute(
        update(Commitment)
        .where(Commitment.promiser_id.in_(source_person_ids), Commitment.user_id == user_id)
        .values(promiser_id=target_person_id, promiser_name=target_person.name)
    )
    await db.execute(
        update(Commitment)
        .where(Commitment.promisee_id.in_(source_person_ids), Commitment.user_id == user_id)
        .values(promisee_id=target_person_id, promisee_name=target_person.name)
    )

    # Delete source people records
    await db.execute(
        delete(Person).where(Person.id.in_(source_person_ids), Person.user_id == user_id)
    )

    audit = AuditEvent(
        user_id=user_id,
        event_type="person_merged",
        entity_type="person",
        entity_id=target_person_id,
        metadata_json=json.dumps({"source_person_ids": source_person_ids}),
    )
    db.add(audit)

    await db.commit()
    await db.refresh(target_person)
    return target_person


# --- PROJECT MANAGEMENT (FR-30) ---
async def create_project(
    db: AsyncSession, user_id: int, name: str, description: str | None = None
) -> Project:
    proj = Project(user_id=user_id, name=name.strip(), description=description)
    db.add(proj)
    await db.commit()
    await db.refresh(proj)
    return proj


async def get_projects(db: AsyncSession, user_id: int) -> list[Project]:
    res = await db.execute(
        select(Project).where(Project.user_id == user_id).order_by(Project.name)
    )
    return list(res.scalars().all())


# --- TOPIC MANAGEMENT (FR-31) ---
async def create_topic(db: AsyncSession, user_id: int, name: str) -> Topic:
    topic = Topic(user_id=user_id, name=name.strip())
    db.add(topic)
    await db.commit()
    await db.refresh(topic)
    return topic


async def get_topics(db: AsyncSession, user_id: int) -> list[Topic]:
    res = await db.execute(
        select(Topic).where(Topic.user_id == user_id).order_by(Topic.name)
    )
    return list(res.scalars().all())


async def merge_topics(
    db: AsyncSession, user_id: int, target_topic_id: int, source_topic_ids: list[int]
) -> Topic:
    t_res = await db.execute(
        select(Topic).where(Topic.id == target_topic_id, Topic.user_id == user_id)
    )
    target_topic = t_res.scalar_one_or_none()
    if not target_topic:
        raise ValueError("Target topic not found or access denied")

    await db.execute(
        update(ConversationTopic)
        .where(ConversationTopic.topic_id.in_(source_topic_ids))
        .values(topic_id=target_topic_id)
    )

    await db.execute(
        delete(Topic).where(Topic.id.in_(source_topic_ids), Topic.user_id == user_id)
    )

    await db.commit()
    await db.refresh(target_topic)
    return target_topic


# --- CONVERSATION SEARCH (FR-32) ---
async def search_conversations(
    db: AsyncSession,
    user_id: int,
    query: str | None = None,
    person_id: int | None = None,
    project_id: int | None = None,
    topic_id: int | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> list[dict[str, Any]]:
    stmt = select(Conversation).where(Conversation.user_id == user_id)

    if project_id is not None:
        stmt = stmt.where(Conversation.project_id == project_id)
    if start_date is not None:
        stmt = stmt.where(Conversation.occurred_at >= start_date)
    if end_date is not None:
        stmt = stmt.where(Conversation.occurred_at <= end_date)

    res = await db.execute(stmt.order_by(Conversation.occurred_at.desc()))
    conversations = res.scalars().all()

    results = []
    q_clean = query.lower().strip() if query else None

    for conv in conversations:
        # Check topic filter
        if topic_id is not None:
            ct_res = await db.execute(
                select(ConversationTopic).where(
                    ConversationTopic.conversation_id == conv.id,
                    ConversationTopic.topic_id == topic_id,
                )
            )
            if not ct_res.scalar_one_or_none():
                continue

        # Check person filter
        if person_id is not None:
            spk_res = await db.execute(
                select(Speaker).where(
                    Speaker.conversation_id == conv.id, Speaker.person_id == person_id
                )
            )
            if not spk_res.scalar_one_or_none():
                continue

        # Fetch MOM summary text if present
        mom_res = await db.execute(select(MOM).where(MOM.conversation_id == conv.id))
        mom = mom_res.scalar_one_or_none()
        mom_summary = mom.summary if mom else ""

        # Fetch transcript text snippets
        snippet = ""
        tr_res = await db.execute(select(Transcript).where(Transcript.conversation_id == conv.id))
        transcript = tr_res.scalar_one_or_none()
        if transcript:
            seg_res = await db.execute(
                select(TranscriptSegment)
                .where(TranscriptSegment.transcript_id == transcript.id)
                .limit(5)
            )
            segments = seg_res.scalars().all()
            texts = []
            for seg in segments:
                pt = None
                for aad in [
                    f"pcma-transcript-{transcript.id}-{seg.chunk_index}-{seg.segment_index}".encode(),
                    transcript.encryption_key_ref.encode("utf-8"),
                ]:
                    try:
                        pt = decrypt_bytes(seg.text_ciphertext, aad).decode("utf-8")
                        break
                    except Exception:
                        continue
                if pt:
                    texts.append(pt)
            snippet = " ".join(texts)

        match = True
        if q_clean:
            combined = (conv.title + " " + mom_summary + " " + snippet).lower()
            if q_clean not in combined:
                match = False

        if match:
            results.append(
                {
                    "conversation_id": conv.id,
                    "title": conv.title,
                    "occurred_at": conv.occurred_at,
                    "project_id": conv.project_id,
                    "summary": mom_summary,
                    "snippet": snippet[:300],
                }
            )

    return results


# --- PERSONAL MEMORY (FR-33) ---
async def get_personal_memories(
    db: AsyncSession,
    user_id: int,
    entity_type: str | None = None,
    entity_id: int | None = None,
    query: str | None = None,
) -> list[PersonalMemory]:
    stmt = select(PersonalMemory).where(PersonalMemory.user_id == user_id)
    if entity_type:
        stmt = stmt.where(PersonalMemory.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(PersonalMemory.entity_id == entity_id)

    res = await db.execute(stmt.order_by(PersonalMemory.created_at.desc()))
    memories = res.scalars().all()

    if query:
        q_lower = query.lower()
        memories = [m for m in memories if q_lower in m.fact_text.lower()]
    return list(memories)
