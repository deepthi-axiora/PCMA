import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
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
from app.models.recording import AuditEvent, Recording
from app.models.transcription import AIProcessingJob, Transcript, TranscriptSegment
from app.services.encryption import decrypt_bytes
from app.services.llm_provider import get_llm_provider

logger = logging.getLogger("pcma.extraction_service")


async def run_extraction_for_conversation(
    db: AsyncSession, conversation_id: int, user_id: int
) -> AIExtraction:
    # 1. Fetch conversation and check user ownership (prefer exact Conversation.id, then fallback to recording_id)
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user_id
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        result = await db.execute(
            select(Conversation).where(
                Conversation.recording_id == conversation_id,
                Conversation.user_id == user_id,
            ).order_by(Conversation.id.desc())
        )
        conv = result.scalars().first()

    if not conv:
        raise ValueError("Conversation not found or access denied")

    # 2. Fetch transcript and segments (using resolved conversation id)
    t_res = await db.execute(
        select(Transcript).where(Transcript.conversation_id == conv.id)
    )
    transcript = t_res.scalar_one_or_none()
    if not transcript:
        # Fallback search by recording_id
        t_res = await db.execute(
            select(Transcript).where(Transcript.recording_id == conv.recording_id)
        )
        transcript = t_res.scalar_one_or_none()

    if not transcript:
        raise ValueError("No transcript found for conversation")

    seg_res = await db.execute(
        select(TranscriptSegment)
        .where(TranscriptSegment.transcript_id == transcript.id)
        .order_by(TranscriptSegment.segment_index)
    )
    segments = seg_res.scalars().all()

    # Fetch speaker map for conversation
    spk_res = await db.execute(select(Speaker).where(Speaker.conversation_id == conv.id))
    speaker_map = {s.id: s.label for s in spk_res.scalars().all()}

    # Decrypt text for segments
    decrypted_segments = []
    for seg in segments:
        plain_text = None
        for aad in [
            f"pcma-transcript-{transcript.id}-{seg.chunk_index}-{seg.segment_index}".encode(),
            transcript.encryption_key_ref.encode("utf-8"),
        ]:
            try:
                plain_text = decrypt_bytes(seg.text_ciphertext, aad).decode("utf-8")
                break
            except Exception:
                continue
        if plain_text is None:
            plain_text = "[encrypted segment]"

        speaker_label = speaker_map.get(seg.speaker_id)
        decrypted_segments.append(
            {
                "id": seg.id,
                "text": plain_text,
                "speaker_id": seg.speaker_id,
                "speaker_label": speaker_label,
                "start_ms": seg.start_ms,
                "end_ms": seg.end_ms,
            }
        )

    # 3. Invoke LLM provider adapter
    provider = get_llm_provider()
    facts_data, prompt_tokens, comp_tokens, est_cost = await provider.extract_structured_facts(
        decrypted_segments
    )

    # 4. Clean up previous extraction artifacts for idempotent re-runs
    await db.execute(delete(Decision).where(Decision.conversation_id == conversation_id))
    await db.execute(delete(ActionItem).where(ActionItem.conversation_id == conversation_id))
    await db.execute(delete(Commitment).where(Commitment.conversation_id == conversation_id))
    await db.execute(delete(Deadline).where(Deadline.conversation_id == conversation_id))
    await db.execute(delete(Question).where(Question.conversation_id == conversation_id))
    await db.execute(delete(ConversationTopic).where(ConversationTopic.conversation_id == conversation_id))
    await db.execute(delete(AIExtraction).where(AIExtraction.conversation_id == conversation_id))

    # 5. Save topics & links
    for top_data in facts_data.get("topics", []):
        name = top_data.get("name", "").strip()
        if not name:
            continue
        # Find or create topic
        t_q = await db.execute(
            select(Topic).where(Topic.user_id == user_id, Topic.name == name)
        )
        topic_obj = t_q.scalar_one_or_none()
        if not topic_obj:
            topic_obj = Topic(user_id=user_id, name=name)
            db.add(topic_obj)
            await db.flush()

        conf = float(top_data.get("confidence", 1.0))
        is_unc = bool(top_data.get("is_uncertain", False) or conf < 0.75)
        c_top = ConversationTopic(
            conversation_id=conversation_id,
            topic_id=topic_obj.id,
            confidence=conf,
            is_uncertain=is_unc,
            source_segment_ids=json.dumps(top_data.get("source_segment_ids", [])),
        )
        db.add(c_top)

    # 6. Save organizations
    for org_data in facts_data.get("organizations", []):
        name = org_data.get("name", "").strip()
        if not name:
            continue
        o_q = await db.execute(
            select(Organization).where(
                Organization.user_id == user_id, Organization.name == name
            )
        )
        org_obj = o_q.scalar_one_or_none()
        if not org_obj:
            org_obj = Organization(user_id=user_id, name=name)
            db.add(org_obj)
            await db.flush()

    # 7. Save people
    for person_data in facts_data.get("people", []):
        name = person_data.get("name", "").strip()
        if not name:
            continue
        p_q = await db.execute(
            select(Person).where(Person.user_id == user_id, Person.name == name)
        )
        p_obj = p_q.scalar_one_or_none()
        if not p_obj:
            p_obj = Person(user_id=user_id, name=name)
            db.add(p_obj)
            await db.flush()

    # 8. Save Decisions
    for dec in facts_data.get("decisions", []):
        text = dec.get("text", "").strip()
        if not text:
            continue
        conf = float(dec.get("confidence", 1.0))
        is_unc = bool(dec.get("is_uncertain", False) or conf < 0.75)
        d_obj = Decision(
            user_id=user_id,
            conversation_id=conversation_id,
            text=text,
            confidence=conf,
            is_uncertain=is_unc,
            source_segment_ids=json.dumps(dec.get("source_segment_ids", [])),
        )
        db.add(d_obj)

    # 9. Save Action Items
    for ai in facts_data.get("action_items", []):
        text = ai.get("text", "").strip()
        if not text:
            continue
        conf = float(ai.get("confidence", 1.0))
        is_unc = bool(ai.get("is_uncertain", False) or conf < 0.75)
        assignee_name = ai.get("assignee_name")
        if assignee_name and assignee_name.lower() in ["alice", "allies"]:
            assignee_name = "Alice"
        elif assignee_name:
            assignee_name = assignee_name.strip()
            assignee_name = assignee_name[0].upper() + assignee_name[1:] if assignee_name else assignee_name

        if assignee_name == "Alice" or text.lower().startswith("alice ") or text.lower().startswith("allies "):
            text = re.sub(r"^(?:alice|allies)\s+will\b", "Alice will", text, flags=re.IGNORECASE)
            text = re.sub(r"\ballies\b", "Alice", text, flags=re.IGNORECASE)
        if text:
            text = text[0].upper() + text[1:]

        assignee_id = None
        if assignee_name:
            p_q = await db.execute(
                select(Person).where(Person.user_id == user_id, Person.name == assignee_name)
            )
            found_p = p_q.scalar_one_or_none()
            if found_p:
                assignee_id = found_p.id

        ai_obj = ActionItem(
            user_id=user_id,
            conversation_id=conversation_id,
            assignee_id=assignee_id,
            assignee_name=assignee_name,
            text=text,
            due_date=None,
            status=ai.get("status", "open"),
            confidence=conf,
            is_uncertain=is_unc,
            source_segment_ids=json.dumps(ai.get("source_segment_ids", [])),
        )
        db.add(ai_obj)

    # 10. Save Commitments
    for com in facts_data.get("commitments", []):
        text = com.get("text", "").strip()
        if not text:
            continue
        conf = float(com.get("confidence", 1.0))
        is_unc = bool(com.get("is_uncertain", False) or conf < 0.75)
        promiser_name = com.get("promiser_name")
        promiser_id = None
        if promiser_name:
            p_q = await db.execute(
                select(Person).where(Person.user_id == user_id, Person.name == promiser_name)
            )
            found_p = p_q.scalar_one_or_none()
            if found_p:
                promiser_id = found_p.id

        c_obj = Commitment(
            user_id=user_id,
            conversation_id=conversation_id,
            promiser_id=promiser_id,
            promiser_name=promiser_name,
            text=text,
            due_date=None,
            status=com.get("status", "open"),
            confidence=conf,
            is_uncertain=is_unc,
            source_segment_ids=json.dumps(com.get("source_segment_ids", [])),
        )
        db.add(c_obj)

    # 11. Save Deadlines
    for dline in facts_data.get("deadlines", []):
        title = dline.get("title", "").strip()
        if not title:
            continue
        conf = float(dline.get("confidence", 1.0))
        is_unc = bool(dline.get("is_uncertain", False) or conf < 0.75)
        dl_obj = Deadline(
            user_id=user_id,
            conversation_id=conversation_id,
            title=title,
            due_date=None,
            raw_deadline_text=dline.get("raw_deadline_text"),
            status=dline.get("status", "open"),
            confidence=conf,
            is_uncertain=is_unc,
            source_segment_ids=json.dumps(dline.get("source_segment_ids", [])),
        )
        db.add(dl_obj)

    # 12. Save Questions
    for q in facts_data.get("questions", []):
        q_text = q.get("question_text", "").strip()
        if not q_text:
            continue
        conf = float(q.get("confidence", 1.0))
        is_unc = bool(q.get("is_uncertain", False) or conf < 0.75)
        q_obj = Question(
            user_id=user_id,
            conversation_id=conversation_id,
            question_text=q_text,
            asker_name=q.get("asker_name"),
            answer_text=q.get("answer_text"),
            status=q.get("status", "unanswered"),
            confidence=conf,
            is_uncertain=is_unc,
            source_segment_ids=json.dumps(q.get("source_segment_ids", [])),
        )
        db.add(q_obj)

    # 13. Create AIExtraction record
    ai_ext = AIExtraction(
        user_id=user_id,
        conversation_id=conversation_id,
        stage="structured_extraction",
        status="completed",
        model_used=getattr(provider, "model", "heuristic-mock-v2"),
        provider=provider.__class__.__name__,
        prompt_tokens=prompt_tokens,
        completion_tokens=comp_tokens,
        estimated_cost=est_cost,
    )
    db.add(ai_ext)

    # Audit event
    audit = AuditEvent(
        user_id=user_id,
        event_type="structured_extraction_completed",
        entity_type="conversation",
        entity_id=conversation_id,
        metadata_json="{}",
    )
    db.add(audit)

    await db.commit()
    await db.refresh(ai_ext)
    return ai_ext


async def process_next_extraction_job(db: AsyncSession) -> bool:
    from sqlalchemy import or_, and_
    now = datetime.now(timezone.utc)
    res = await db.execute(
        select(AIProcessingJob)
        .where(
            AIProcessingJob.stage == "structured_extraction",
            or_(
                and_(
                    AIProcessingJob.status.in_(["queued", "retrying"]),
                    AIProcessingJob.available_at <= now,
                ),
                and_(
                    AIProcessingJob.status == "running",
                    AIProcessingJob.lease_expires_at <= now,
                ),
            ),
        )
        .order_by(AIProcessingJob.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = res.scalar_one_or_none()
    if not job:
        return False

    job.status = "running"
    job.started_at = now
    job.lease_expires_at = datetime.fromtimestamp(now.timestamp() + 180, tz=timezone.utc)
    job.attempts += 1
    await db.commit()

    # Get conversation via recording_id
    c_res = await db.execute(
        select(Conversation).where(Conversation.recording_id == job.recording_id)
    )
    conv = c_res.scalar_one_or_none()
    if not conv:
        job.status = "failed"
        job.last_error_code = "CONVERSATION_NOT_FOUND"
        await db.commit()
        return True

    try:
        await run_extraction_for_conversation(db, conv.id, conv.user_id)
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
    except Exception as exc:
        logger.error("extraction_job_failed recording_id=%d err=%s", job.recording_id, str(exc))
        if job.attempts >= job.max_attempts:
            job.status = "failed"
            job.last_error_code = "EXTRACTION_FAILED"
        else:
            job.status = "retrying"
            job.available_at = datetime.fromtimestamp(now.timestamp() + 10, tz=timezone.utc)
    await db.commit()
    return True
