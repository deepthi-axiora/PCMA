from datetime import datetime, timezone
import pytest
from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models import ActionItem, Conversation, Person, Recording, User, Topic
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
from app.models.memory_search import PersonalMemory


@pytest.mark.asyncio
async def test_people_management_and_merge():
    async with AsyncSessionLocal() as db:
        user = User(auth_id="auth0|user_people_1")
        db.add(user)
        await db.flush()

        p1 = await create_person(db, user.id, "Alice Smith")
        p2 = await create_person(db, user.id, "Alice S.")
        assert len(await get_people(db, user.id)) == 2

        rec = Recording(user_id=user.id, duration_ms=5000, state="completed")
        db.add(rec)
        await db.flush()

        conv = Conversation(
            user_id=user.id,
            recording_id=rec.id,
            title="Design Review",
            occurred_at=datetime.now(timezone.utc),
        )
        db.add(conv)
        await db.flush()

        ai = ActionItem(
            user_id=user.id,
            conversation_id=conv.id,
            assignee_id=p2.id,
            assignee_name="Alice S.",
            text="Update Figma mockups",
            status="open",
            confidence=0.9,
            is_uncertain=False,
            source_segment_ids="[1]",
        )
        db.add(ai)
        await db.commit()

        # Merge p2 into p1
        merged_person = await merge_people(db, user.id, p1.id, [p2.id])
        assert merged_person.id == p1.id

        # Verify action item was reassigned
        ai_res = await db.execute(select(ActionItem).where(ActionItem.id == ai.id))
        reassigned_ai = ai_res.scalar_one()
        assert reassigned_ai.assignee_id == p1.id

        # Verify only 1 person remains
        people = await get_people(db, user.id)
        assert len(people) == 1
        assert people[0].name == "Alice Smith"


@pytest.mark.asyncio
async def test_project_and_topic_management():
    async with AsyncSessionLocal() as db:
        user = User(auth_id="auth0|user_proj_1")
        db.add(user)
        await db.flush()

        proj = await create_project(db, user.id, "PCMA Core", "Core Memory Engine")
        assert proj.id is not None
        assert len(await get_projects(db, user.id)) == 1

        t1 = await create_topic(db, user.id, "Database Architecture")
        t2 = await create_topic(db, user.id, "DB Arch")
        assert len(await get_topics(db, user.id)) == 2

        merged_topic = await merge_topics(db, user.id, t1.id, [t2.id])
        assert merged_topic.id == t1.id
        assert len(await get_topics(db, user.id)) == 1


@pytest.mark.asyncio
async def test_conversation_search_and_personal_memory():
    async with AsyncSessionLocal() as db:
        user = User(auth_id="auth0|user_search_1")
        db.add(user)
        await db.flush()

        rec = Recording(user_id=user.id, duration_ms=5000, state="completed")
        db.add(rec)
        await db.flush()

        conv = Conversation(
            user_id=user.id,
            recording_id=rec.id,
            title="Q3 Security Audit",
            occurred_at=datetime.now(timezone.utc),
        )
        db.add(conv)
        await db.flush()

        mem = PersonalMemory(
            user_id=user.id,
            conversation_id=conv.id,
            entity_type="security",
            fact_text="SOC2 compliance audit completed in August.",
            provenance_json='{"source": "audit_log"}',
        )
        db.add(mem)
        await db.commit()

        # Search conversations
        results = await search_conversations(db, user.id, query="Security")
        assert len(results) == 1
        assert results[0]["title"] == "Q3 Security Audit"

        # Memory recall
        memories = await get_personal_memories(db, user.id, query="compliance")
        assert len(memories) == 1
        assert "SOC2" in memories[0].fact_text
