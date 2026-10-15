from datetime import datetime, timezone
import pytest
from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models import ActionItem, Conversation, Decision, MOM, Recording, User
from app.services.mom_service import (
    approve_mom,
    edit_mom,
    generate_mom_for_conversation,
    get_mom_by_conversation,
    get_mom_edit_history,
)


@pytest.mark.asyncio
async def test_generate_edit_and_approve_mom():
    async with AsyncSessionLocal() as db:
        user = User(auth_id="auth0|user_mom_1")
        db.add(user)
        await db.flush()

        rec = Recording(user_id=user.id, duration_ms=10000, state="completed")
        db.add(rec)
        await db.flush()

        conv = Conversation(
            user_id=user.id,
            recording_id=rec.id,
            title="Q4 Strategy",
            occurred_at=datetime.now(timezone.utc),
        )
        db.add(conv)
        await db.flush()

        dec = Decision(
            user_id=user.id,
            conversation_id=conv.id,
            text="Adopt cloud-native stack",
            confidence=0.9,
            is_uncertain=False,
            source_segment_ids="[1]",
        )
        db.add(dec)
        await db.commit()

        # Generate MOM
        mom = await generate_mom_for_conversation(db, conv.id, user.id)
        assert mom.id is not None
        assert mom.status == "draft"
        assert "Q4 Strategy" in mom.title

        # Retrieve MOM
        retrieved = await get_mom_by_conversation(db, conv.id, user.id)
        assert retrieved.id == mom.id
        assert len(retrieved.sections) >= 5

        # Edit MOM
        edited = await edit_mom(
            db, mom.id, user.id, title="Updated Strategy MOM", summary="Custom user summary"
        )
        assert edited.title == "Updated Strategy MOM"
        assert edited.is_user_edited is True

        # Check Edit History
        history = await get_mom_edit_history(db, mom.id, user.id)
        assert len(history) == 2

        # Approve MOM
        approved = await approve_mom(db, mom.id, user.id)
        assert approved.status == "approved"
        assert approved.approved_at is not None


@pytest.mark.asyncio
async def test_mom_user_scoping_isolation():
    async with AsyncSessionLocal() as db:
        user_a = User(auth_id="auth0|mom_a")
        user_b = User(auth_id="auth0|mom_b")
        db.add_all([user_a, user_b])
        await db.flush()

        rec = Recording(user_id=user_a.id, duration_ms=5000, state="completed")
        db.add(rec)
        await db.flush()

        conv = Conversation(
            user_id=user_a.id,
            recording_id=rec.id,
            title="User A Meeting",
            occurred_at=datetime.now(timezone.utc),
        )
        db.add(conv)
        await db.commit()

        mom = await generate_mom_for_conversation(db, conv.id, user_a.id)

        # User B attempting to edit or approve User A's MOM must fail
        with pytest.raises(ValueError):
            await edit_mom(db, mom.id, user_b.id, title="Hacked")

        with pytest.raises(ValueError):
            await approve_mom(db, mom.id, user_b.id)


@pytest.mark.asyncio
async def test_recording_id_resolves_to_conversation_and_generates_mom():
    async with AsyncSessionLocal() as db:
        user = User(auth_id="auth0|user_rec_fallback")
        db.add(user)
        await db.flush()

        rec = Recording(user_id=user.id, duration_ms=12000, state="completed")
        db.add(rec)
        await db.flush()

        conv = Conversation(
            user_id=user.id,
            recording_id=rec.id,
            title="Sprint 11 Sync",
            occurred_at=datetime.now(timezone.utc),
        )
        db.add(conv)
        await db.flush()

        dec = Decision(
            user_id=user.id,
            conversation_id=conv.id,
            text="Ship safe ID resolution",
            confidence=0.95,
            is_uncertain=False,
            source_segment_ids="[1]",
        )
        db.add(dec)
        await db.commit()

        # 1. Generate MOM using recording_id
        mom_from_rec = await generate_mom_for_conversation(db, rec.id, user.id)
        assert mom_from_rec is not None
        assert mom_from_rec.conversation_id == conv.id
        assert "Sprint 11 Sync" in mom_from_rec.title

        # 2. Retrieve MOM using recording_id
        retrieved_from_rec = await get_mom_by_conversation(db, rec.id, user.id)
        assert retrieved_from_rec is not None
        assert retrieved_from_rec.id == mom_from_rec.id

        # 3. Retrieve MOM using conversation.id
        retrieved_from_conv = await get_mom_by_conversation(db, conv.id, user.id)
        assert retrieved_from_conv is not None
        assert retrieved_from_conv.id == mom_from_rec.id


@pytest.mark.asyncio
async def test_overlapping_recording_and_conversation_ids_prefers_exact_conversation():
    async with AsyncSessionLocal() as db:
        user = User(auth_id="auth0|user_overlap_priority")
        db.add(user)
        await db.flush()

        # rec1 has id 500, rec2 has id 600
        rec1 = Recording(id=500, user_id=user.id, duration_ms=5000, state="completed")
        rec2 = Recording(id=600, user_id=user.id, duration_ms=6000, state="completed")
        db.add_all([rec1, rec2])
        await db.flush()

        # conv1 has id 600 and recording_id 500
        conv1 = Conversation(
            id=600,
            user_id=user.id,
            recording_id=rec1.id,  # 500
            title="Conv 1 Title",
            occurred_at=datetime.now(timezone.utc),
        )
        # conv2 has id 700 and recording_id 600 (overlaps with conv1.id!)
        conv2 = Conversation(
            id=700,
            user_id=user.id,
            recording_id=rec2.id,  # 600 == conv1.id
            title="Conv 2 Title",
            occurred_at=datetime.now(timezone.utc),
        )
        db.add_all([conv1, conv2])
        await db.flush()

        dec1 = Decision(user_id=user.id, conversation_id=conv1.id, text="Decision 1", confidence=1.0)
        dec2 = Decision(user_id=user.id, conversation_id=conv2.id, text="Decision 2", confidence=1.0)
        db.add_all([dec1, dec2])
        await db.commit()

        # Generate MOM for both
        mom1 = await generate_mom_for_conversation(db, conv1.id, user.id)
        mom2 = await generate_mom_for_conversation(db, conv2.id, user.id)

        # Querying conv1.id MUST return conv1's MOM, NOT conv2's MOM (even though conv2.recording_id == conv1.id!)
        resolved_mom = await get_mom_by_conversation(db, conv1.id, user.id)
        assert resolved_mom is not None
        assert resolved_mom.id == mom1.id
        assert resolved_mom.conversation_id == conv1.id


@pytest.mark.asyncio
async def test_nonexistent_conversation_returns_error():
    async with AsyncSessionLocal() as db:
        user = User(auth_id="auth0|user_not_found_check")
        db.add(user)
        await db.commit()

        with pytest.raises(ValueError, match="Conversation not found or access denied"):
            await get_mom_by_conversation(db, 999999, user.id)

        with pytest.raises(ValueError, match="Conversation not found or access denied"):
            await generate_mom_for_conversation(db, 999999, user.id)


@pytest.mark.asyncio
async def test_ownership_checks_prevent_access_to_another_users_conversation():
    async with AsyncSessionLocal() as db:
        user_owner = User(auth_id="auth0|owner_user")
        user_other = User(auth_id="auth0|other_user")
        db.add_all([user_owner, user_other])
        await db.flush()

        rec = Recording(user_id=user_owner.id, duration_ms=4000, state="completed")
        db.add(rec)
        await db.flush()

        conv = Conversation(
            user_id=user_owner.id,
            recording_id=rec.id,
            title="Private Owner Meeting",
            occurred_at=datetime.now(timezone.utc),
        )
        db.add(conv)
        await db.commit()

        # Other user querying by exact conversation ID must fail
        with pytest.raises(ValueError, match="Conversation not found or access denied"):
            await get_mom_by_conversation(db, conv.id, user_other.id)

        with pytest.raises(ValueError, match="Conversation not found or access denied"):
            await generate_mom_for_conversation(db, conv.id, user_other.id)

        # Other user querying by recording ID fallback must also fail
        with pytest.raises(ValueError, match="Conversation not found or access denied"):
            await get_mom_by_conversation(db, rec.id, user_other.id)

        with pytest.raises(ValueError, match="Conversation not found or access denied"):
            await generate_mom_for_conversation(db, rec.id, user_other.id)


@pytest.mark.asyncio
async def test_refresh_existing_draft_mom_without_duplicates():
    async with AsyncSessionLocal() as db:
        user = User(auth_id="auth0|user_mom_refresh_test")
        db.add(user)
        await db.flush()

        rec = Recording(user_id=user.id, duration_ms=8000, state="completed")
        db.add(rec)
        await db.flush()

        conv = Conversation(
            user_id=user.id,
            recording_id=rec.id,
            title="Sprint Planning",
            occurred_at=datetime.now(timezone.utc),
        )
        db.add(conv)
        await db.flush()

        dec = Decision(
            user_id=user.id,
            conversation_id=conv.id,
            text="Adopt new architecture",
            confidence=0.9,
            is_uncertain=False,
            source_segment_ids="[1]",
        )
        db.add(dec)
        await db.commit()

    async with AsyncSessionLocal() as db:
        # 1. Initial MOM generation: 1 decision, 0 action items
        initial_mom = await generate_mom_for_conversation(db, conv.id, user.id)
        assert initial_mom.status == "draft"
        assert "1 decision(s)" in initial_mom.summary
        assert "0 action item(s)" in initial_mom.summary
        initial_mom_id = initial_mom.id

        # 2. Add an action item to the conversation
        ai = ActionItem(
            user_id=user.id,
            conversation_id=conv.id,
            text="allies will do the deployment by Friday",
            assignee_name="allies",
            status="open",
            confidence=0.9,
            is_uncertain=False,
            source_segment_ids="[2]",
        )
        db.add(ai)
        await db.commit()

    async with AsyncSessionLocal() as db:
        # 3. Refresh draft MOM
        refreshed_mom = await generate_mom_for_conversation(db, conv.id, user.id, refresh_draft=True)
        # MUST have identical ID (no duplicate MOM row)
        assert refreshed_mom.id == initial_mom_id
        assert refreshed_mom.status == "draft"
        assert "1 decision(s)" in refreshed_mom.summary
        assert "1 action item(s)" in refreshed_mom.summary

        # Verify only one MOM exists in database for this conversation
        all_moms = (await db.execute(select(MOM).where(MOM.conversation_id == conv.id))).scalars().all()
        assert len(all_moms) == 1

        # Verify sections refreshed
        sec_map = {s.section_type: s.content_json for s in refreshed_mom.sections}
        assert "allies will do the deployment by Friday" in sec_map["action_items"]
        assert "Adopt new architecture" in sec_map["decisions"]


@pytest.mark.asyncio
async def test_refresh_never_overwrites_approved_mom():
    async with AsyncSessionLocal() as db:
        user = User(auth_id="auth0|user_mom_approved_protection")
        db.add(user)
        await db.flush()

        rec = Recording(user_id=user.id, duration_ms=5000, state="completed")
        db.add(rec)
        await db.flush()

        conv = Conversation(
            user_id=user.id,
            recording_id=rec.id,
            title="Final Review",
            occurred_at=datetime.now(timezone.utc),
        )
        db.add(conv)
        await db.flush()

        dec = Decision(
            user_id=user.id,
            conversation_id=conv.id,
            text="Finalized Release Plan",
            confidence=0.95,
            is_uncertain=False,
            source_segment_ids="[1]",
        )
        db.add(dec)
        await db.commit()

    async with AsyncSessionLocal() as db:
        mom = await generate_mom_for_conversation(db, conv.id, user.id)
        approved = await approve_mom(db, mom.id, user.id)
        assert approved.status == "approved"
        approved_time = approved.approved_at

        # Add more facts after approval
        ai = ActionItem(
            user_id=user.id,
            conversation_id=conv.id,
            text="Unrelated post-approval task",
            assignee_name="Bob",
            status="open",
            confidence=0.9,
            is_uncertain=False,
            source_segment_ids="[2]",
        )
        db.add(ai)
        await db.commit()

    async with AsyncSessionLocal() as db:
        # Re-running generate on approved MOM must NEVER overwrite it
        result = await generate_mom_for_conversation(db, conv.id, user.id, refresh_draft=True)
        assert result.id == mom.id
        assert result.status == "approved"
        assert result.approved_at is not None
        assert result.approved_at.replace(tzinfo=timezone.utc) == approved_time
        assert "0 action item(s)" in result.summary  # unchanged, approved content preserved


