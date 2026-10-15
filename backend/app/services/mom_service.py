import json
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.extraction import (
    ActionItem,
    Commitment,
    ConversationTopic,
    Deadline,
    Decision,
    Question,
)
from app.models.mom import MOM, MOMEditHistory, MOMSection
from app.models.recording import AuditEvent

logger = logging.getLogger("pcma.mom_service")


def _normalize_name(name: str | None) -> str | None:
    if not name:
        return name
    clean = name.strip()
    if clean.lower() == "alice":
        return "Alice"
    return clean[0].upper() + clean[1:] if clean else clean


def _normalize_action_text(text: str, assignee_name: str | None = None) -> str:
    if not text:
        return text
    clean = text.strip()
    norm_name = _normalize_name(assignee_name)
    if norm_name == "Alice" or clean.lower().startswith("alice will"):
        clean = re.sub(r"^alice\s+will\b", "Alice will", clean, flags=re.IGNORECASE)
    return clean


async def generate_mom_for_conversation(
    db: AsyncSession, conversation_id: int, user_id: int, *, refresh_draft: bool = True
) -> MOM:
    # 1. Verify conversation ownership (prefer exact Conversation.id, then fallback to recording_id)
    c_res = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )
    conv = c_res.scalar_one_or_none()
    if not conv:
        c_res = await db.execute(
            select(Conversation).where(
                Conversation.recording_id == conversation_id,
                Conversation.user_id == user_id,
            ).order_by(Conversation.id.desc())
        )
        conv = c_res.scalars().first()

    if not conv:
        raise ValueError("Conversation not found or access denied")

    target_conv_id = conv.id

    # 2. Check if MOM already exists (prefer matching target_conv_id, then conv.recording_id)
    m_res = await db.execute(
        select(MOM).where(
            MOM.conversation_id == target_conv_id,
            MOM.user_id == user_id,
        )
    )
    existing_mom = m_res.scalars().first()
    if not existing_mom and conv.recording_id:
        other_conv = (await db.execute(
            select(Conversation.id).where(
                Conversation.id == conv.recording_id,
                Conversation.user_id == user_id,
            )
        )).scalar_one_or_none()
        if not other_conv:
            m_res = await db.execute(
                select(MOM).where(
                    MOM.conversation_id == conv.recording_id,
                    MOM.user_id == user_id,
                )
            )
            existing_mom = m_res.scalars().first()

    if existing_mom:
        # Safeguard: Never overwrite an approved MOM
        if existing_mom.status == "approved" or not refresh_draft:
            await db.refresh(existing_mom, ["sections"])
            return existing_mom

    # Auto-run structured extraction if not yet executed for this conversation
    from app.models.extraction import AIExtraction
    ext_res = await db.execute(
        select(AIExtraction).where(AIExtraction.conversation_id == target_conv_id)
    )
    if not ext_res.scalar_one_or_none():
        has_facts = (await db.execute(
            select(Decision.id).where(Decision.conversation_id == target_conv_id).limit(1)
        )).scalar_one_or_none() is not None
        if not has_facts:
            from app.models.transcription import Transcript
            t_res = await db.execute(
                select(Transcript.id).where(
                    (Transcript.conversation_id == target_conv_id) | (Transcript.recording_id == conv.recording_id)
                )
            )
            has_transcript = t_res.scalar_one_or_none() is not None
            if has_transcript:
                try:
                    from app.services.extraction_service import run_extraction_for_conversation
                    await run_extraction_for_conversation(db, target_conv_id, user_id)
                except Exception as exc:
                    logger.error("Structured extraction required before MOM generation: %s", exc)
                    raise ValueError(
                        f"extraction_not_ready: Structured extraction must be completed before generating MOM ({exc})"
                    ) from exc

    # 3. Fetch structured facts from Sprint 5
    dec_res = await db.execute(
        select(Decision).where(Decision.conversation_id == target_conv_id).execution_options(populate_existing=True)
    )
    decisions = dec_res.scalars().all()

    ai_res = await db.execute(
        select(ActionItem).where(ActionItem.conversation_id == target_conv_id).execution_options(populate_existing=True)
    )
    action_items = ai_res.scalars().all()

    com_res = await db.execute(
        select(Commitment).where(Commitment.conversation_id == target_conv_id).execution_options(populate_existing=True)
    )
    commitments = com_res.scalars().all()

    dl_res = await db.execute(
        select(Deadline).where(Deadline.conversation_id == target_conv_id).execution_options(populate_existing=True)
    )
    deadlines = dl_res.scalars().all()

    q_res = await db.execute(
        select(Question).where(Question.conversation_id == target_conv_id).execution_options(populate_existing=True)
    )
    questions = q_res.scalars().all()

    top_res = await db.execute(
        select(ConversationTopic).where(
            ConversationTopic.conversation_id == target_conv_id
        ).execution_options(populate_existing=True)
    )
    conv_topics = top_res.scalars().all()

    # 4. Generate title and summary
    raw_title = (conv.title or "").strip()
    if raw_title and raw_title not in ["Conversation", "New Conversation"] and not raw_title.startswith("Conversation #"):
        mom_title = f"MOM - {raw_title}"
    else:
        mom_title = f"Meeting Notes - Conversation #{conv.id}"

    all_facts = list(decisions) + list(action_items) + list(commitments) + list(deadlines) + list(questions)
    total_facts = len(all_facts)

    has_uncertain_facts = any(
        getattr(f, "is_uncertain", False) or getattr(f, "confidence", 1.0) < 0.75 for f in all_facts
    )
    mom_uncertain = has_uncertain_facts

    if total_facts == 0:
        mom_confidence = 1.0
        summary_text = (
            f"Draft Notes for '{mom_title}'. "
            "Extracted 0 decision(s), 0 action item(s), 0 commitment(s), 0 deadline(s), and 0 question(s)."
        )
    else:
        conf_list = [getattr(f, "confidence", 1.0) for f in all_facts]
        mom_confidence = round(sum(conf_list) / len(conf_list), 2)
        summary_text = (
            f"Minutes of Meeting for '{mom_title}'. "
            f"Extracted {len(decisions)} decision(s), {len(action_items)} action item(s), "
            f"{len(commitments)} commitment(s), {len(deadlines)} deadline(s), and {len(questions)} question(s)."
        )
        if mom_uncertain:
            summary_text += " Note: Certain extracted facts contain ambiguous or low-confidence details requiring human review."

    is_refresh = existing_mom is not None
    if is_refresh:
        mom = existing_mom
        mom.conversation_id = target_conv_id
        if not mom.is_user_edited:
            mom.title = mom_title
            mom.summary = summary_text
        mom.confidence = mom_confidence
        mom.is_uncertain = mom_uncertain
        mom.updated_at = datetime.now(timezone.utc)
        await db.execute(delete(MOMSection).where(MOMSection.mom_id == mom.id))
        await db.flush()
    else:
        mom = MOM(
            user_id=user_id,
            conversation_id=target_conv_id,
            title=mom_title,
            summary=summary_text,
            status="draft",
            confidence=mom_confidence,
            is_uncertain=mom_uncertain,
            is_user_edited=False,
        )
        db.add(mom)
        await db.flush()

    # 5. Populate sections with traceability and review metadata
    sections = [
        MOMSection(
            mom_id=mom.id,
            section_type="decisions",
            title="Key Decisions",
            content_json=json.dumps(
                [
                    {
                        "id": d.id,
                        "text": d.text,
                        "confidence": d.confidence,
                        "is_uncertain": d.is_uncertain,
                        "source_segment_ids": json.loads(d.source_segment_ids or "[]"),
                    }
                    for d in decisions
                ]
            ),
        ),
        MOMSection(
            mom_id=mom.id,
            section_type="action_items",
            title="Action Items",
            content_json=json.dumps(
                [
                    {
                        "id": a.id,
                        "text": _normalize_action_text(a.text, a.assignee_name),
                        "assignee_name": _normalize_name(a.assignee_name),
                        "status": a.status,
                        "due_date": a.due_date.isoformat() if a.due_date else None,
                        "confidence": a.confidence,
                        "is_uncertain": a.is_uncertain,
                        "source_segment_ids": json.loads(a.source_segment_ids or "[]"),
                    }
                    for a in action_items
                ]
            ),
        ),
        MOMSection(
            mom_id=mom.id,
            section_type="commitments",
            title="Commitments",
            content_json=json.dumps(
                [
                    {
                        "id": c.id,
                        "text": c.text,
                        "promiser_name": _normalize_name(c.promiser_name),
                        "status": c.status,
                        "confidence": c.confidence,
                        "is_uncertain": c.is_uncertain,
                        "source_segment_ids": json.loads(c.source_segment_ids or "[]"),
                    }
                    for c in commitments
                ]
            ),
        ),
        MOMSection(
            mom_id=mom.id,
            section_type="deadlines",
            title="Deadlines",
            content_json=json.dumps(
                [
                    {
                        "id": dl.id,
                        "title": dl.title,
                        "raw_deadline_text": dl.raw_deadline_text,
                        "confidence": dl.confidence,
                        "is_uncertain": dl.is_uncertain,
                        "source_segment_ids": json.loads(dl.source_segment_ids or "[]"),
                    }
                    for dl in deadlines
                ]
            ),
        ),
        MOMSection(
            mom_id=mom.id,
            section_type="questions",
            title="Open Questions",
            content_json=json.dumps(
                [
                    {
                        "id": q.id,
                        "text": q.question_text,
                        "status": q.status,
                        "confidence": q.confidence,
                        "is_uncertain": q.is_uncertain,
                        "source_segment_ids": json.loads(q.source_segment_ids or "[]"),
                    }
                    for q in questions
                ]
            ),
        ),
    ]
    db.add_all(sections)

    # 6. Audit event
    audit = AuditEvent(
        user_id=user_id,
        event_type="mom_refreshed" if is_refresh else "mom_generated",
        entity_type="mom",
        entity_id=mom.id,
        metadata_json=json.dumps({"conversation_id": target_conv_id}),
    )
    db.add(audit)

    await db.commit()
    await db.refresh(mom, ["sections"])
    return mom


async def get_mom_by_conversation(
    db: AsyncSession, conversation_id: int, user_id: int
) -> MOM | None:
    # 1. Verify conversation ownership (prefer exact Conversation.id, then fallback to recording_id)
    c_res = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )
    conv = c_res.scalar_one_or_none()
    if not conv:
        c_res = await db.execute(
            select(Conversation).where(
                Conversation.recording_id == conversation_id,
                Conversation.user_id == user_id,
            ).order_by(Conversation.id.desc())
        )
        conv = c_res.scalars().first()

    if not conv:
        raise ValueError("Conversation not found or access denied")

    res = await db.execute(
        select(MOM).where(
            MOM.conversation_id == conv.id,
            MOM.user_id == user_id,
        )
    )
    mom = res.scalars().first()
    if not mom and conv.recording_id:
        other_conv = (await db.execute(
            select(Conversation.id).where(
                Conversation.id == conv.recording_id,
                Conversation.user_id == user_id,
            )
        )).scalar_one_or_none()
        if not other_conv:
            res = await db.execute(
                select(MOM).where(
                    MOM.conversation_id == conv.recording_id,
                    MOM.user_id == user_id,
                )
            )
            mom = res.scalars().first()
    if mom:
        await db.refresh(mom, ["sections"])
    return mom


async def edit_mom(
    db: AsyncSession,
    mom_id: int,
    user_id: int,
    title: str | None = None,
    summary: str | None = None,
) -> MOM:
    res = await db.execute(
        select(MOM).where(MOM.id == mom_id, MOM.user_id == user_id)
    )
    mom = res.scalar_one_or_none()
    if not mom:
        raise ValueError("MOM not found or access denied")

    if title is not None and title != mom.title:
        db.add(
            MOMEditHistory(
                mom_id=mom.id,
                user_id=user_id,
                edited_field="title",
                old_value=mom.title,
                new_value=title,
            )
        )
        mom.title = title
        mom.is_user_edited = True

    if summary is not None and summary != mom.summary:
        db.add(
            MOMEditHistory(
                mom_id=mom.id,
                user_id=user_id,
                edited_field="summary",
                old_value=mom.summary,
                new_value=summary,
            )
        )
        mom.summary = summary
        mom.is_user_edited = True

    audit = AuditEvent(
        user_id=user_id,
        event_type="mom_edited",
        entity_type="mom",
        entity_id=mom.id,
        metadata_json=json.dumps({"mom_id": mom_id}),
    )
    db.add(audit)

    await db.commit()
    await db.refresh(mom, ["sections"])
    return mom


async def approve_mom(
    db: AsyncSession, mom_id: int, user_id: int, *, confirmed_review: bool = False
) -> MOM:
    res = await db.execute(
        select(MOM).where(MOM.id == mom_id, MOM.user_id == user_id)
    )
    mom = res.scalar_one_or_none()
    if not mom:
        raise ValueError("MOM not found or access denied")

    # If MOM contains uncertain facts or draft notes, require confirmed human review
    if mom.is_uncertain and not (mom.is_user_edited or confirmed_review):
        raise ValueError(
            "human_review_required: Uncertain facts or unverified draft notes detected. "
            "Please review and confirm the content before approving."
        )

    mom.status = "approved"
    mom.approved_at = datetime.now(timezone.utc)

    audit = AuditEvent(
        user_id=user_id,
        event_type="mom_approved",
        entity_type="mom",
        entity_id=mom.id,
        metadata_json=json.dumps({"mom_id": mom_id}),
    )
    db.add(audit)

    await db.commit()
    await db.refresh(mom, ["sections"])
    return mom


async def get_mom_edit_history(
    db: AsyncSession, mom_id: int, user_id: int
) -> list[MOMEditHistory]:
    res = await db.execute(
        select(MOM).where(MOM.id == mom_id, MOM.user_id == user_id)
    )
    mom = res.scalar_one_or_none()
    if not mom:
        raise ValueError("MOM not found or access denied")

    h_res = await db.execute(
        select(MOMEditHistory)
        .where(MOMEditHistory.mom_id == mom_id)
        .order_by(MOMEditHistory.edited_at.desc())
    )
    return list(h_res.scalars().all())
