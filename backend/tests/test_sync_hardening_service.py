from datetime import datetime, timezone
import pytest
from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models import AuditEvent, Commitment, Conversation, Recording, User
from app.services.sync_hardening_service import get_sync_status, process_batch_sync


@pytest.mark.asyncio
async def test_batch_synchronization_and_status():
    async with AsyncSessionLocal() as db:
        user = User(auth_id="auth0|user_sync_1")
        db.add(user)
        await db.flush()

        rec = Recording(user_id=user.id, duration_ms=5000, state="completed")
        db.add(rec)
        await db.flush()

        conv = Conversation(
            user_id=user.id,
            recording_id=rec.id,
            title="Sync Test",
            occurred_at=datetime.now(timezone.utc),
        )
        db.add(conv)
        await db.flush()

        c = Commitment(
            user_id=user.id,
            conversation_id=conv.id,
            text="Sync testing task",
            status="open",
            confidence=0.9,
            is_uncertain=False,
            source_segment_ids="[1]",
        )
        db.add(c)
        await db.commit()

        # Batch sync payload
        sync_items = [
            {
                "action": "update_commitment_status",
                "payload": {"commitment_id": c.id, "status": "fulfilled"},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            {
                "action": "log_offline_event",
                "payload": {"event_type": "offline_audio_cached", "size_bytes": 10240},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        ]

        result = await process_batch_sync(db, user.id, sync_items)
        assert result["processed_count"] == 2
        assert result["failed_count"] == 0

        # Verify commitment status updated
        await db.refresh(c)
        assert c.status == "fulfilled"

        # Verify sync status endpoint data
        status_info = await get_sync_status(db, user.id)
        assert status_info["status"] == "in_sync"
        assert status_info["open_recordings_count"] == 0
