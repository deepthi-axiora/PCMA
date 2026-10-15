import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recording import AuditEvent, Recording
from app.services.commitment_reminder_service import update_commitment_status

logger = logging.getLogger("pcma.sync_hardening_service")


async def process_batch_sync(
    db: AsyncSession, user_id: int, items: list[dict[str, Any]]
) -> dict[str, Any]:
    processed = 0
    errors = []

    for item in items:
        action = item.get("action")
        payload = item.get("payload", {})
        client_timestamp = item.get("timestamp")

        try:
            if action == "update_commitment_status":
                commitment_id = payload.get("commitment_id")
                new_status = payload.get("status")
                if commitment_id and new_status:
                    await update_commitment_status(db, commitment_id, user_id, new_status)
                    processed += 1

            elif action == "log_offline_event":
                event_type = payload.get("event_type", "offline_client_action")
                audit = AuditEvent(
                    user_id=user_id,
                    event_type=event_type,
                    entity_type="client_sync",
                    metadata_json=json.dumps(payload),
                )
                db.add(audit)
                processed += 1

            else:
                # Idempotent no-op for unsupported or unknown action
                processed += 1

        except Exception as exc:
            logger.error("sync_item_failed action=%s err=%s", action, str(exc))
            errors.append({"action": action, "error": str(exc)})

    await db.commit()

    return {
        "user_id": user_id,
        "processed_count": processed,
        "failed_count": len(errors),
        "errors": errors,
        "synced_at": datetime.now(timezone.utc),
    }


async def get_sync_status(db: AsyncSession, user_id: int) -> dict[str, Any]:
    # Check open recordings
    res = await db.execute(
        select(Recording).where(
            Recording.user_id == user_id, Recording.state.in_(["active", "paused"])
        )
    )
    open_recordings = len(res.scalars().all())

    return {
        "user_id": user_id,
        "open_recordings_count": open_recordings,
        "last_synced_at": datetime.now(timezone.utc),
        "status": "in_sync",
    }
