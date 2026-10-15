from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models import ActionItem, Commitment, Conversation, Recording, User, Reminder
from app.services.commitment_reminder_service import (
    cancel_reminder,
    create_reminder,
    get_user_action_items,
    get_user_commitments,
    process_due_reminders,
    update_action_item_status,
    update_commitment_status,
)


@pytest.mark.asyncio
async def test_commitment_status_derivation_and_tracking():
    async with AsyncSessionLocal() as db:
        user = User(auth_id="auth0|user_comm_1")
        db.add(user)
        await db.flush()

        rec = Recording(user_id=user.id, duration_ms=5000, state="completed")
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

        now = datetime.now(timezone.utc)
        due_tomorrow_dt = now + timedelta(hours=20)
        overdue_dt = now - timedelta(hours=10)

        # 1. Commitment due tomorrow
        c1 = Commitment(
            user_id=user.id,
            conversation_id=conv.id,
            text="Deliver deployment script",
            due_date=due_tomorrow_dt,
            status="open",
            confidence=0.9,
            is_uncertain=False,
            source_segment_ids="[1]",
        )
        # 2. Overdue Commitment
        c2 = Commitment(
            user_id=user.id,
            conversation_id=conv.id,
            text="Send project specs",
            due_date=overdue_dt,
            status="open",
            confidence=0.9,
            is_uncertain=False,
            source_segment_ids="[2]",
        )
        db.add_all([c1, c2])
        await db.commit()

        # Query commitments with status derivation
        items = await get_user_commitments(db, user.id)
        assert len(items) == 2

        overdue_items = await get_user_commitments(db, user.id, status_filter="overdue")
        assert len(overdue_items) == 1
        assert overdue_items[0]["text"] == "Send project specs"

        due_items = await get_user_commitments(db, user.id, status_filter="due-tomorrow")
        assert len(due_items) == 1
        assert due_items[0]["text"] == "Deliver deployment script"

        # Update status
        updated = await update_commitment_status(db, c2.id, user.id, "fulfilled")
        assert updated.status == "fulfilled"


@pytest.mark.asyncio
async def test_deterministic_reminder_scheduling_and_worker_dispatch():
    async with AsyncSessionLocal() as db:
        user = User(auth_id="auth0|user_rem_1")
        db.add(user)
        await db.flush()

        now = datetime.now(timezone.utc)
        past_time = now - timedelta(minutes=5)

        # Create past due reminder
        r1 = await create_reminder(
            db, user.id, title="Review Pull Request", remind_at=past_time, user_timezone="America/New_York"
        )
        assert r1.status == "pending"

        # Dispatch due reminders
        dispatched_count = await process_due_reminders(db)
        assert dispatched_count >= 1

        # Check reminder status updated to 'sent'
        r_res = await db.execute(select(Reminder).where(Reminder.id == r1.id))
        updated_r = r_res.scalar_one()
        assert updated_r.status == "sent"


@pytest.mark.asyncio
async def test_reminder_cancel_and_ownership():
    async with AsyncSessionLocal() as db:
        user_a = User(auth_id="auth0|user_rem_a")
        user_b = User(auth_id="auth0|user_rem_b")
        db.add_all([user_a, user_b])
        await db.flush()

        r = await create_reminder(
            db, user_a.id, title="Submit Report", remind_at=datetime.now(timezone.utc) + timedelta(days=1)
        )

        # User B attempting to cancel User A's reminder must fail
        with pytest.raises(ValueError):
            await cancel_reminder(db, r.id, user_b.id)

        # User A cancelling own reminder
        cancelled = await cancel_reminder(db, r.id, user_a.id)
        assert cancelled.status == "cancelled"
