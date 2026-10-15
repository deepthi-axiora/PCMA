import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Person, Speaker
from app.models.extraction import (
    ActionItem,
    AIExtraction,
    Commitment,
    ConversationTopic,
    Deadline,
    Decision,
    Organization,
    Question,
    Topic,
)
from app.models.memory_search import PersonalMemory, Project
from app.models.mom import MOM, MOMEditHistory, MOMSection
from app.models.recording import AudioFile, AuditEvent, ConsentRecord, Recording
from app.models.sharing_export import ExportJob, MOMRecipient
from app.models.commitments_reminders import Reminder
from app.models.transcription import AIProcessingJob, Transcript, TranscriptSegment
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services.audio_storage import delete_audio

logger = logging.getLogger("pcma.data_control_service")


async def delete_user_data(db: AsyncSession, user_id: int) -> dict[str, Any]:
    """FR-42: Purge user-owned data across all system modules while preserving append-only audit retention."""

    # 1. Reminders
    await db.execute(delete(Reminder).where(Reminder.user_id == user_id))

    # 2. Personal Memories & Projects
    await db.execute(delete(PersonalMemory).where(PersonalMemory.user_id == user_id))
    await db.execute(delete(Project).where(Project.user_id == user_id))

    # 3. Sharing & Export Jobs
    await db.execute(delete(MOMRecipient).where(MOMRecipient.user_id == user_id))
    await db.execute(delete(ExportJob).where(ExportJob.user_id == user_id))

    # 4. MOMs & Edit Histories
    mom_ids_res = await db.execute(select(MOM.id).where(MOM.user_id == user_id))
    mom_ids = list(mom_ids_res.scalars().all())
    if mom_ids:
        await db.execute(delete(MOMEditHistory).where(MOMEditHistory.mom_id.in_(mom_ids)))
        await db.execute(delete(MOMSection).where(MOMSection.mom_id.in_(mom_ids)))
        await db.execute(delete(MOM).where(MOM.user_id == user_id))

    # 5. Extracted Facts
    await db.execute(delete(AIExtraction).where(AIExtraction.user_id == user_id))
    await db.execute(delete(Question).where(Question.user_id == user_id))
    await db.execute(delete(Deadline).where(Deadline.user_id == user_id))
    await db.execute(delete(Commitment).where(Commitment.user_id == user_id))
    await db.execute(delete(ActionItem).where(ActionItem.user_id == user_id))
    await db.execute(delete(Decision).where(Decision.user_id == user_id))
    await db.execute(delete(Organization).where(Organization.user_id == user_id))
    await db.execute(delete(Topic).where(Topic.user_id == user_id))

    # 6. Conversations & Speakers
    conv_ids_res = await db.execute(select(Conversation.id).where(Conversation.user_id == user_id))
    conv_ids = list(conv_ids_res.scalars().all())
    if conv_ids:
        await db.execute(delete(ConversationTopic).where(ConversationTopic.conversation_id.in_(conv_ids)))
        await db.execute(delete(Speaker).where(Speaker.conversation_id.in_(conv_ids)))
        await db.execute(delete(Conversation).where(Conversation.user_id == user_id))

    await db.execute(delete(Person).where(Person.user_id == user_id))

    # 7. Recordings, Audio Files & Physical Audio Storage (FR-42 Physical Deletion)
    rec_ids_res = await db.execute(select(Recording.id).where(Recording.user_id == user_id))
    rec_ids = list(rec_ids_res.scalars().all())
    if rec_ids:
        # Collect physical audio storage references for user's recordings only
        af_res = await db.execute(select(AudioFile.storage_ref).where(AudioFile.recording_id.in_(rec_ids)))
        storage_refs = list(af_res.scalars().all())
        for ref in storage_refs:
            try:
                delete_audio(ref)
            except Exception as exc:
                logger.warning("physical_audio_file_deletion_warning ref=%s err=%s", ref, str(exc))

        await db.execute(delete(AudioFile).where(AudioFile.recording_id.in_(rec_ids)))
        await db.execute(delete(ConsentRecord).where(ConsentRecord.recording_id.in_(rec_ids)))
        await db.execute(delete(AIProcessingJob).where(AIProcessingJob.recording_id.in_(rec_ids)))
        await db.execute(delete(Transcript).where(Transcript.recording_id.in_(rec_ids)))
        await db.execute(delete(Recording).where(Recording.user_id == user_id))

    # Immutable Audit Log entry for compliance
    audit = AuditEvent(
        user_id=user_id,
        event_type="user_data_deleted",
        entity_type="user",
        entity_id=user_id,
        metadata_json=json.dumps({"purged_at": datetime.now(timezone.utc).isoformat()}),
    )
    db.add(audit)

    await db.commit()
    return {"user_id": user_id, "status": "data_deleted", "deleted_at": datetime.now(timezone.utc)}


async def export_user_data_package(db: AsyncSession, user_id: int) -> dict[str, Any]:
    """FR-43: Comprehensive user data export package."""

    u_res = await db.execute(select(User).where(User.id == user_id))
    user = u_res.scalar_one_or_none()
    if not user:
        raise ValueError("User not found")

    p_res = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = p_res.scalar_one_or_none()

    convs_res = await db.execute(select(Conversation).where(Conversation.user_id == user_id))
    convs = convs_res.scalars().all()
    convs_data = [{"id": c.id, "title": c.title, "occurred_at": c.occurred_at.isoformat()} for c in convs]

    moms_res = await db.execute(select(MOM).where(MOM.user_id == user_id))
    moms = moms_res.scalars().all()
    moms_data = [{"id": m.id, "title": m.title, "summary": m.summary, "status": m.status} for m in moms]

    coms_res = await db.execute(select(Commitment).where(Commitment.user_id == user_id))
    coms = coms_res.scalars().all()
    coms_data = [{"id": c.id, "text": c.text, "status": c.status} for c in coms]

    rem_res = await db.execute(select(Reminder).where(Reminder.user_id == user_id))
    rems = rem_res.scalars().all()
    rems_data = [{"id": r.id, "title": r.title, "remind_at": r.remind_at.isoformat()} for r in rems]

    export_package = {
        "user": {
            "id": user.id,
            "auth_id": user.auth_id,
            "created_at": user.created_at.isoformat(),
            "profile": {
                "jurisdiction": profile.jurisdiction if profile else None,
            },
        },
        "conversations": convs_data,
        "minutes_of_meeting": moms_data,
        "commitments": coms_data,
        "reminders": rems_data,
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }

    audit = AuditEvent(
        user_id=user_id,
        event_type="user_data_exported",
        entity_type="user",
        entity_id=user_id,
        metadata_json=json.dumps({"exported_items": len(convs_data) + len(moms_data)}),
    )
    db.add(audit)

    await db.commit()
    return export_package


async def delete_user_account(db: AsyncSession, user_id: int) -> dict[str, Any]:
    """FR-44: Complete account deletion lifecycle preserving append-only audit records without PII."""

    # Purge user data first
    await delete_user_data(db, user_id)

    # Record account deletion audit log prior to user removal
    audit = AuditEvent(
        user_id=user_id,
        event_type="user_account_deleted",
        entity_type="user",
        entity_id=user_id,
        metadata_json=json.dumps({"account_deleted_at": datetime.now(timezone.utc).isoformat()}),
    )
    db.add(audit)
    await db.flush()

    # Scrub PII (user_id) from AuditEvents to satisfy append-only audit retention compliance without storing PII
    await db.execute(update(AuditEvent).where(AuditEvent.user_id == user_id).values(user_id=None))

    # Delete UserProfile & User record
    await db.execute(delete(UserProfile).where(UserProfile.user_id == user_id))
    await db.execute(delete(User).where(User.id == user_id))

    await db.commit()
    return {"user_id": user_id, "status": "account_deleted", "deleted_at": datetime.now(timezone.utc)}
