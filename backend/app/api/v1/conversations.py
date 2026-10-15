import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("pcma.conversations")

from app.core.security import get_current_user
from app.database.session import get_db
from app.models import (
    ActionItem,
    AIExtraction,
    Commitment,
    Conversation,
    ConversationTopic,
    Deadline,
    Decision,
    MOM,
    Person,
    Question,
    Recording,
    Speaker,
    Transcript,
    TranscriptSegment,
    User,
)
from app.schemas.conversation import ConversationResponse
from app.schemas.extraction import (
    ActionItemResponse,
    AIExtractionResponse,
    CommitmentResponse,
    ConversationExtractionsResponse,
    DeadlineResponse,
    DecisionResponse,
    QuestionResponse,
    TopicResponse,
)
from app.schemas.memory_search import PersonResponse
from app.schemas.transcription import TranscriptSegmentCorrectionRequest, TranscriptSegmentResponse
from app.services.encryption import decrypt_bytes
from app.services.extraction_service import run_extraction_for_conversation
from app.services.recording_service import RecordingError
from app.services.transcription_service import correct_transcript_segment

router = APIRouter(prefix="/conversations", tags=["Conversations & Intelligence"])


async def _get_user_conversation(
    db: AsyncSession, conversation_id: int, user_id: int
) -> Conversation:
    # 1. Exact match by Conversation.id
    res = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
    )
    conv = res.scalar_one_or_none()

    # 2. Explicit fallback by Conversation.recording_id only when no exact conversation exists
    if not conv:
        res = await db.execute(
            select(Conversation).where(
                Conversation.recording_id == conversation_id,
                Conversation.user_id == user_id,
            ).order_by(Conversation.id.desc())
        )
        conv = res.scalars().first()

    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or access denied",
        )
    return conv


async def _build_conversation_response(
    db: AsyncSession, conv: Conversation
) -> ConversationResponse:
    # 1. Recording status & state
    rec_res = await db.execute(select(Recording).where(Recording.id == conv.recording_id))
    rec = rec_res.scalar_one_or_none()
    rec_state = rec.state if rec else None
    rec_status = rec.status if rec else None
    display_status = rec_state or rec_status or "completed"

    # 2. Snippet
    snippet = None
    tr_res = await db.execute(select(Transcript).where(Transcript.conversation_id == conv.id))
    transcript = tr_res.scalar_one_or_none()
    if not transcript and conv.recording_id:
        tr_res = await db.execute(select(Transcript).where(Transcript.recording_id == conv.recording_id))
        transcript = tr_res.scalar_one_or_none()

    if transcript:
        seg_res = await db.execute(
            select(TranscriptSegment)
            .where(TranscriptSegment.transcript_id == transcript.id)
            .order_by(TranscriptSegment.start_ms)
            .limit(3)
        )
        segments = seg_res.scalars().all()
        texts = []
        for seg in segments:
            try:
                aad = f"pcma-transcript-{transcript.id}-{seg.chunk_index}-{seg.segment_index}".encode()
                pt = decrypt_bytes(seg.text_ciphertext, aad).decode("utf-8")
                texts.append(pt)
            except Exception:
                pass
        if texts:
            snippet = " ".join(texts)

    if not snippet:
        mom_res = await db.execute(select(MOM).where(MOM.conversation_id == conv.id))
        mom = mom_res.scalar_one_or_none()
        if mom and mom.summary:
            snippet = mom.summary

    # 3. Topics
    ct_res = await db.execute(
        select(ConversationTopic).where(ConversationTopic.conversation_id == conv.id)
    )
    conv_topics = ct_res.scalars().all()
    topic_responses = []
    for ct in conv_topics:
        await db.refresh(ct, ["topic"])
        topic_responses.append(
            TopicResponse(
                id=ct.topic.id,
                name=ct.topic.name,
                confidence=ct.confidence,
                is_uncertain=ct.is_uncertain,
                source_segment_ids=json.loads(ct.source_segment_ids or "[]"),
            )
        )

    # 4. Decisions
    d_res = await db.execute(select(Decision).where(Decision.conversation_id == conv.id))
    dec_responses = [
        DecisionResponse(
            id=d.id,
            conversation_id=d.conversation_id,
            text=d.text,
            confidence=d.confidence,
            is_uncertain=d.is_uncertain,
            source_segment_ids=json.loads(d.source_segment_ids or "[]"),
            created_at=d.created_at,
        )
        for d in d_res.scalars().all()
    ]

    # 5. Action Items
    ai_res = await db.execute(select(ActionItem).where(ActionItem.conversation_id == conv.id))
    ai_responses = [
        ActionItemResponse(
            id=a.id,
            conversation_id=a.conversation_id,
            assignee_id=a.assignee_id,
            assignee_name=a.assignee_name,
            text=a.text,
            due_date=a.due_date,
            status=a.status,
            confidence=a.confidence,
            is_uncertain=a.is_uncertain,
            source_segment_ids=json.loads(a.source_segment_ids or "[]"),
            created_at=a.created_at,
        )
        for a in ai_res.scalars().all()
    ]

    # 6. Commitments
    c_res = await db.execute(select(Commitment).where(Commitment.conversation_id == conv.id))
    c_responses = [
        CommitmentResponse(
            id=c.id,
            conversation_id=c.conversation_id,
            promiser_id=c.promiser_id,
            promiser_name=c.promiser_name,
            promisee_id=c.promisee_id,
            promisee_name=c.promisee_name,
            text=c.text,
            due_date=c.due_date,
            status=c.status,
            confidence=c.confidence,
            is_uncertain=c.is_uncertain,
            source_segment_ids=json.loads(c.source_segment_ids or "[]"),
            created_at=c.created_at,
        )
        for c in c_res.scalars().all()
    ]

    # 7. Deadlines
    dl_res = await db.execute(select(Deadline).where(Deadline.conversation_id == conv.id))
    dl_responses = [
        DeadlineResponse(
            id=dl.id,
            conversation_id=dl.conversation_id,
            title=dl.title,
            due_date=dl.due_date,
            raw_deadline_text=dl.raw_deadline_text,
            status=dl.status,
            confidence=dl.confidence,
            is_uncertain=dl.is_uncertain,
            source_segment_ids=json.loads(dl.source_segment_ids or "[]"),
            created_at=dl.created_at,
        )
        for dl in dl_res.scalars().all()
    ]

    # 8. Questions
    q_res = await db.execute(select(Question).where(Question.conversation_id == conv.id))
    q_responses = [
        QuestionResponse(
            id=q.id,
            conversation_id=q.conversation_id,
            question_text=q.question_text,
            asker_name=q.asker_name,
            answer_text=q.answer_text,
            status=q.status,
            confidence=q.confidence,
            is_uncertain=q.is_uncertain,
            source_segment_ids=json.loads(q.source_segment_ids or "[]"),
            created_at=q.created_at,
        )
        for q in q_res.scalars().all()
    ]

    # 9. People
    spk_res = await db.execute(
        select(Speaker).where(Speaker.conversation_id == conv.id, Speaker.person_id.isnot(None))
    )
    speakers = spk_res.scalars().all()
    people_responses = []
    for spk in speakers:
        if spk.person_id:
            p_res = await db.execute(select(Person).where(Person.id == spk.person_id))
            person = p_res.scalar_one_or_none()
            if person:
                people_responses.append(PersonResponse.model_validate(person))

    return ConversationResponse(
        id=conv.id,
        recording_id=conv.recording_id,
        user_id=conv.user_id,
        title=conv.title,
        occurred_at=conv.occurred_at,
        created_at=conv.created_at,
        snippet=snippet,
        status=display_status,
        state=rec_state,
        topics=topic_responses,
        action_items=ai_responses,
        commitments=c_responses,
        decisions=dec_responses,
        deadlines=dl_responses,
        questions=q_responses,
        people=people_responses,
        organizations=[],
    )


@router.get("", response_model=list[ConversationResponse])
@router.get("/", response_model=list[ConversationResponse], include_in_schema=False)
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.occurred_at.desc(), Conversation.id.desc())
    )
    conversations = res.scalars().all()
    return [await _build_conversation_response(db, conv) for conv in conversations]


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await _get_user_conversation(db, conversation_id, current_user.id)
    return await _build_conversation_response(db, conv)


@router.post("/{conversation_id}/extract", response_model=AIExtractionResponse)
@router.post("/{conversation_id}/process-extraction", response_model=AIExtractionResponse, include_in_schema=False)
async def extract_facts(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await _get_user_conversation(db, conversation_id, current_user.id)
    try:
        extraction = await run_extraction_for_conversation(
            db, conv.id, current_user.id
        )
        # If an existing draft MOM exists for this conversation, refresh it from new facts
        from app.services.mom_service import generate_mom_for_conversation
        try:
            await generate_mom_for_conversation(db, conv.id, current_user.id, refresh_draft=True)
        except Exception as mom_exc:
            logger.warning("Auto-refreshing draft MOM after extraction skipped: %s", mom_exc)

        return AIExtractionResponse.model_validate(extraction)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {str(exc)}",
        )


@router.get("/{conversation_id}/extractions", response_model=ConversationExtractionsResponse)
async def get_extractions(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await _get_user_conversation(db, conversation_id, current_user.id)
    target_id = conv.id

    # Topics
    ct_res = await db.execute(
        select(ConversationTopic)
        .where(ConversationTopic.conversation_id == target_id)
    )
    conv_topics = ct_res.scalars().all()
    topic_responses = []
    for ct in conv_topics:
        await db.refresh(ct, ["topic"])
        topic_responses.append(
            TopicResponse(
                id=ct.topic.id,
                name=ct.topic.name,
                confidence=ct.confidence,
                is_uncertain=ct.is_uncertain,
                source_segment_ids=json.loads(ct.source_segment_ids or "[]"),
            )
        )

    # Decisions
    d_res = await db.execute(
        select(Decision).where(Decision.conversation_id == target_id)
    )
    decisions = d_res.scalars().all()
    dec_responses = [
        DecisionResponse(
            id=d.id,
            conversation_id=d.conversation_id,
            text=d.text,
            confidence=d.confidence,
            is_uncertain=d.is_uncertain,
            source_segment_ids=json.loads(d.source_segment_ids or "[]"),
            created_at=d.created_at,
        )
        for d in decisions
    ]

    # Action Items
    ai_res = await db.execute(
        select(ActionItem).where(ActionItem.conversation_id == target_id)
    )
    action_items = ai_res.scalars().all()
    ai_responses = [
        ActionItemResponse(
            id=a.id,
            conversation_id=a.conversation_id,
            assignee_id=a.assignee_id,
            assignee_name=a.assignee_name,
            text=a.text,
            due_date=a.due_date,
            status=a.status,
            confidence=a.confidence,
            is_uncertain=a.is_uncertain,
            source_segment_ids=json.loads(a.source_segment_ids or "[]"),
            created_at=a.created_at,
        )
        for a in action_items
    ]

    # Commitments
    c_res = await db.execute(
        select(Commitment).where(Commitment.conversation_id == target_id)
    )
    commitments = c_res.scalars().all()
    c_responses = [
        CommitmentResponse(
            id=c.id,
            conversation_id=c.conversation_id,
            promiser_id=c.promiser_id,
            promiser_name=c.promiser_name,
            promisee_id=c.promisee_id,
            promisee_name=c.promisee_name,
            text=c.text,
            due_date=c.due_date,
            status=c.status,
            confidence=c.confidence,
            is_uncertain=c.is_uncertain,
            source_segment_ids=json.loads(c.source_segment_ids or "[]"),
            created_at=c.created_at,
        )
        for c in commitments
    ]

    # Deadlines
    dl_res = await db.execute(
        select(Deadline).where(Deadline.conversation_id == target_id)
    )
    deadlines = dl_res.scalars().all()
    dl_responses = [
        DeadlineResponse(
            id=dl.id,
            conversation_id=dl.conversation_id,
            title=dl.title,
            due_date=dl.due_date,
            raw_deadline_text=dl.raw_deadline_text,
            status=dl.status,
            confidence=dl.confidence,
            is_uncertain=dl.is_uncertain,
            source_segment_ids=json.loads(dl.source_segment_ids or "[]"),
            created_at=dl.created_at,
        )
        for dl in deadlines
    ]

    # Questions
    q_res = await db.execute(
        select(Question).where(Question.conversation_id == target_id)
    )
    questions = q_res.scalars().all()
    q_responses = [
        QuestionResponse(
            id=q.id,
            conversation_id=q.conversation_id,
            question_text=q.question_text,
            asker_name=q.asker_name,
            answer_text=q.answer_text,
            status=q.status,
            confidence=q.confidence,
            is_uncertain=q.is_uncertain,
            source_segment_ids=json.loads(q.source_segment_ids or "[]"),
            created_at=q.created_at,
        )
        for q in questions
    ]

    # AI Extraction Job
    ext_res = await db.execute(
        select(AIExtraction).where(AIExtraction.conversation_id == target_id)
    )
    ext = ext_res.scalar_one_or_none()

    return ConversationExtractionsResponse(
        conversation_id=target_id,
        topics=topic_responses,
        decisions=dec_responses,
        action_items=ai_responses,
        commitments=c_responses,
        deadlines=dl_responses,
        questions=q_responses,
        extraction=AIExtractionResponse.model_validate(ext) if ext else None,
    )


@router.patch("/{conversation_id}/segments/{segment_id}", response_model=TranscriptSegmentResponse)
async def correct_conversation_segment(
    conversation_id: int,
    segment_id: int,
    request: TranscriptSegmentCorrectionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await correct_transcript_segment(
            db,
            conversation_id,
            segment_id,
            current_user.id,
            request.text,
            re_extract=request.re_extract,
        )
    except RecordingError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": error.code, "message": error.message},
        )

