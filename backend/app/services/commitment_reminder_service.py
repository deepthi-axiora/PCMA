import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.commitments_reminders import Reminder
from app.models.extraction import ActionItem, Commitment, Deadline
from app.models.recording import AuditEvent

logger = logging.getLogger("pcma.commitment_reminder_service")


# --- COMMITMENTS & ACTION ITEMS STATUS DERIVATION (FR-34) ---
def compute_item_status(due_date: datetime | None, current_status: str, now: datetime) -> str:
    if current_status in ["fulfilled", "completed", "cancelled", "met", "missed"]:
        return current_status
    if not due_date:
        return "open"

    if due_date < now:
        return "overdue"

    time_diff = due_date - now
    if timedelta(hours=12) <= time_diff <= timedelta(hours=36):
        return "due-tomorrow"
    if time_diff <= timedelta(hours=24):
        return "due"
    return "open"


async def get_user_commitments(
    db: AsyncSession, user_id: int, status_filter: str | None = None
) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    res = await db.execute(
        select(Commitment)
        .where(Commitment.user_id == user_id)
        .order_by(Commitment.created_at.desc())
    )
    commitments = res.scalars().all()

    output = []
    for c in commitments:
        derived_status = compute_item_status(c.due_date, c.status, now)
        if status_filter and status_filter.lower() != derived_status:
            continue
        output.append(
            {
                "id": c.id,
                "conversation_id": c.conversation_id,
                "promiser_id": c.promiser_id,
                "promiser_name": c.promiser_name,
                "promisee_id": c.promisee_id,
                "promisee_name": c.promisee_name,
                "text": c.text,
                "due_date": c.due_date,
                "status": derived_status,
                "confidence": c.confidence,
                "is_uncertain": c.is_uncertain,
                "created_at": c.created_at,
            }
        )
    return output


async def update_commitment_status(
    db: AsyncSession, commitment_id: int, user_id: int, new_status: str
) -> Commitment:
    res = await db.execute(
        select(Commitment).where(Commitment.id == commitment_id, Commitment.user_id == user_id)
    )
    c = res.scalar_one_or_none()
    if not c:
        raise ValueError("Commitment not found or access denied")

    c.status = new_status
    audit = AuditEvent(
        user_id=user_id,
        event_type="commitment_status_updated",
        entity_type="commitment",
        entity_id=c.id,
        metadata_json=json.dumps({"new_status": new_status}),
    )
    db.add(audit)
    await db.commit()
    await db.refresh(c)
    return c


async def get_user_action_items(
    db: AsyncSession, user_id: int, status_filter: str | None = None
) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    res = await db.execute(
        select(ActionItem)
        .where(ActionItem.user_id == user_id)
        .order_by(ActionItem.created_at.desc())
    )
    action_items = res.scalars().all()

    output = []
    for a in action_items:
        derived_status = compute_item_status(a.due_date, a.status, now)
        if status_filter and status_filter.lower() != derived_status:
            continue
        output.append(
            {
                "id": a.id,
                "conversation_id": a.conversation_id,
                "assignee_id": a.assignee_id,
                "assignee_name": a.assignee_name,
                "text": a.text,
                "due_date": a.due_date,
                "status": derived_status,
                "confidence": a.confidence,
                "is_uncertain": a.is_uncertain,
                "created_at": a.created_at,
            }
        )
    return output


async def update_action_item_status(
    db: AsyncSession, action_item_id: int, user_id: int, new_status: str
) -> ActionItem:
    res = await db.execute(
        select(ActionItem).where(
            ActionItem.id == action_item_id, ActionItem.user_id == user_id
        )
    )
    a = res.scalar_one_or_none()
    if not a:
        raise ValueError("Action item not found or access denied")

    a.status = new_status
    audit = AuditEvent(
        user_id=user_id,
        event_type="action_item_status_updated",
        entity_type="action_item",
        entity_id=a.id,
        metadata_json=json.dumps({"new_status": new_status}),
    )
    db.add(audit)
    await db.commit()
    await db.refresh(a)
    return a


# --- DETERMINISTIC REMINDER GENERATION & SCHEDULING (FR-35) ---
async def create_reminder(
    db: AsyncSession,
    user_id: int,
    title: str,
    remind_at: datetime,
    user_timezone: str = "UTC",
    commitment_id: int | None = None,
    action_item_id: int | None = None,
    deadline_id: int | None = None,
    priority: str = "normal",
) -> Reminder:
    reminder = Reminder(
        user_id=user_id,
        commitment_id=commitment_id,
        action_item_id=action_item_id,
        deadline_id=deadline_id,
        title=title.strip(),
        remind_at=remind_at,
        timezone=user_timezone,
        status="pending",
        priority=priority,
    )
    db.add(reminder)
    await db.flush()

    audit = AuditEvent(
        user_id=user_id,
        event_type="reminder_scheduled",
        entity_type="reminder",
        entity_id=reminder.id,
        metadata_json=json.dumps({"remind_at": remind_at.isoformat(), "timezone": user_timezone}),
    )
    db.add(audit)

    await db.commit()
    await db.refresh(reminder)
    return reminder


async def process_due_reminders(db: AsyncSession) -> int:
    now = datetime.now(timezone.utc)
    res = await db.execute(
        select(Reminder).where(Reminder.status == "pending", Reminder.remind_at <= now)
    )
    reminders = res.scalars().all()

    processed_count = 0
    for r in reminders:
        r.status = "sent"
        # Pure non-sensitive notification payload (does not contain transcript text)
        audit = AuditEvent(
            user_id=r.user_id,
            event_type="reminder_sent",
            entity_type="reminder",
            entity_id=r.id,
            metadata_json=json.dumps({"reminder_id": r.id, "title": r.title}),
        )
        db.add(audit)
        processed_count += 1

    await db.commit()
    return processed_count


async def get_user_reminders(db: AsyncSession, user_id: int) -> list[Reminder]:
    res = await db.execute(
        select(Reminder)
        .where(Reminder.user_id == user_id)
        .order_by(Reminder.remind_at.asc())
    )
    return list(res.scalars().all())


async def cancel_reminder(db: AsyncSession, reminder_id: int, user_id: int) -> Reminder:
    res = await db.execute(
        select(Reminder).where(Reminder.id == reminder_id, Reminder.user_id == user_id)
    )
    r = res.scalar_one_or_none()
    if not r:
        raise ValueError("Reminder not found or access denied")

    r.status = "cancelled"
    await db.commit()
    await db.refresh(r)
    return r
