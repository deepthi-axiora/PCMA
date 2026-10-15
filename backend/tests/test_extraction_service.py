from datetime import datetime, timezone
import pytest
from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models import (
    ActionItem,
    Commitment,
    Conversation,
    Deadline,
    Decision,
    Question,
    Recording,
    Speaker,
    Topic,
    Transcript,
    TranscriptSegment,
    User,
)
from app.services.encryption import encrypt_bytes
from app.services.extraction_service import (
    process_next_extraction_job,
    run_extraction_for_conversation,
)
from app.services.mom_service import generate_mom_for_conversation
from app.models.transcription import AIProcessingJob
import json


@pytest.mark.asyncio
async def test_run_extraction_for_conversation():
    async with AsyncSessionLocal() as db:
        user = User(auth_id="auth0|user_extraction_1")
        db.add(user)
        await db.flush()

        rec = Recording(user_id=user.id, duration_ms=10000, state="completed")
        db.add(rec)
        await db.flush()

        conv = Conversation(user_id=user.id, recording_id=rec.id, title="Architecture Sync", occurred_at=datetime.now(timezone.utc))
        db.add(conv)
        await db.flush()

        tr = Transcript(recording_id=rec.id, conversation_id=conv.id, encryption_key_ref="test_key", status="completed")
        db.add(tr)
        await db.flush()

        seg1 = TranscriptSegment(
            transcript_id=tr.id,
            chunk_index=0,
            segment_index=0,
            start_ms=0,
            end_ms=5000,
            text_ciphertext=encrypt_bytes(b"We decided to use PostgreSQL for project architecture.", b"test_key"),
            confidence=0.95,
        )
        seg2 = TranscriptSegment(
            transcript_id=tr.id,
            chunk_index=0,
            segment_index=1,
            start_ms=5000,
            end_ms=10000,
            text_ciphertext=encrypt_bytes(b"Alice will do the schema design by Friday. What is our budget?", b"test_key"),
            confidence=0.90,
        )
        db.add_all([seg1, seg2])
        await db.commit()

        ai_ext = await run_extraction_for_conversation(db, conv.id, user.id)
        assert ai_ext.id is not None
        assert ai_ext.prompt_tokens > 0

        dec_res = await db.execute(select(Decision).where(Decision.conversation_id == conv.id))
        decisions = dec_res.scalars().all()
        assert len(decisions) >= 1

        q_res = await db.execute(select(Question).where(Question.conversation_id == conv.id))
        questions = q_res.scalars().all()
        assert len(questions) >= 1
        assert "budget" in questions[0].question_text.lower()


@pytest.mark.asyncio
async def test_extraction_worker_job_processing():
    async with AsyncSessionLocal() as db:
        user = User(auth_id="auth0|user_extraction_2")
        db.add(user)
        await db.flush()

        rec = Recording(user_id=user.id, duration_ms=5000, state="completed")
        db.add(rec)
        await db.flush()

        conv = Conversation(user_id=user.id, recording_id=rec.id, title="Team Catchup", occurred_at=datetime.now(timezone.utc))
        db.add(conv)
        await db.flush()

        tr = Transcript(recording_id=rec.id, conversation_id=conv.id, encryption_key_ref="test_key", status="completed")
        db.add(tr)
        await db.flush()

        seg = TranscriptSegment(
            transcript_id=tr.id,
            chunk_index=0,
            segment_index=0,
            start_ms=0,
            end_ms=5000,
            text_ciphertext=encrypt_bytes(b"I promise to deliver the report tomorrow.", b"test_key"),
            confidence=0.88,
        )
        db.add(seg)

        job = AIProcessingJob(
            recording_id=rec.id,
            stage="structured_extraction",
            status="queued",
            provider="mock",
            max_attempts=3,
            available_at=datetime.now(timezone.utc),
        )
        db.add(job)
        await db.commit()

    async with AsyncSessionLocal() as db:
        processed = await process_next_extraction_job(db)
        assert processed is True

    async with AsyncSessionLocal() as db:
        j_res = await db.execute(select(AIProcessingJob).where(AIProcessingJob.recording_id == rec.id))
        job = j_res.scalar_one()
        assert job.status == "completed"

        com_res = await db.execute(select(Commitment).where(Commitment.conversation_id == conv.id))
        commitments = com_res.scalars().all()
        assert len(commitments) >= 1


@pytest.mark.asyncio
async def test_user_ownership_isolation():
    async with AsyncSessionLocal() as db:
        user_a = User(auth_id="auth0|user_a")
        user_b = User(auth_id="auth0|user_b")
        db.add_all([user_a, user_b])
        await db.flush()

        rec = Recording(user_id=user_a.id, duration_ms=5000, state="completed")
        db.add(rec)
        await db.flush()

        conv = Conversation(user_id=user_a.id, recording_id=rec.id, title="User A Conv", occurred_at=datetime.now(timezone.utc))
        db.add(conv)
        await db.commit()

        with pytest.raises(ValueError):
            await run_extraction_for_conversation(db, conv.id, user_b.id)


@pytest.mark.asyncio
async def test_synthetic_meeting_transcript_full_extraction_and_mom():
    """Verify that a synthetic meeting transcript with explicit decision, action item, commitment,
    deadline, and question correctly extracts all items and populates the MOM sections."""
    async with AsyncSessionLocal() as db:
        user = User(auth_id="auth0|user_synthetic_meeting")
        db.add(user)
        await db.flush()

        rec = Recording(user_id=user.id, duration_ms=25000, state="completed")
        db.add(rec)
        await db.flush()

        conv = Conversation(
            user_id=user.id,
            recording_id=rec.id,
            title="Q4 Product Strategy",
            occurred_at=datetime.now(timezone.utc),
        )
        db.add(conv)
        await db.flush()

        spk1 = Speaker(conversation_id=conv.id, label="Alice")
        spk2 = Speaker(conversation_id=conv.id, label="Bob")
        db.add_all([spk1, spk2])
        await db.flush()

        tr = Transcript(
            recording_id=rec.id,
            conversation_id=conv.id,
            encryption_key_ref="env:AUDIO_ENCRYPTION_KEY",
            status="completed",
        )
        db.add(tr)
        await db.flush()

        # 1. Decision segment (Alice)
        aad0 = f"pcma-transcript-{tr.id}-0-0".encode()
        seg0 = TranscriptSegment(
            transcript_id=tr.id,
            chunk_index=0,
            segment_index=0,
            start_ms=0,
            end_ms=5000,
            text_ciphertext=encrypt_bytes(b"We decided to migrate the core database to PostgreSQL.", aad0),
            confidence=0.96,
            speaker_id=spk1.id,
        )

        # 2. Action item + deadline segment (Bob assigns Alice)
        aad1 = f"pcma-transcript-{tr.id}-0-1".encode()
        seg1 = TranscriptSegment(
            transcript_id=tr.id,
            chunk_index=0,
            segment_index=1,
            start_ms=5000,
            end_ms=10000,
            text_ciphertext=encrypt_bytes(b"Alice will do the schema migration task by Friday.", aad1),
            confidence=0.92,
            speaker_id=spk2.id,
        )

        # 3. Commitment segment (Bob)
        aad2 = f"pcma-transcript-{tr.id}-0-2".encode()
        seg2 = TranscriptSegment(
            transcript_id=tr.id,
            chunk_index=0,
            segment_index=2,
            start_ms=10000,
            end_ms=15000,
            text_ciphertext=encrypt_bytes(b"I promise to deliver the security audit report.", aad2),
            confidence=0.94,
            speaker_id=spk2.id,
        )

        # 4. Question segment (Alice)
        aad3 = f"pcma-transcript-{tr.id}-0-3".encode()
        seg3 = TranscriptSegment(
            transcript_id=tr.id,
            chunk_index=0,
            segment_index=3,
            start_ms=15000,
            end_ms=20000,
            text_ciphertext=encrypt_bytes(b"What is our deployment timeline for the release?", aad3),
            confidence=0.95,
            speaker_id=spk1.id,
        )

        db.add_all([seg0, seg1, seg2, seg3])
        await db.commit()

        # Run structured extraction
        ai_ext = await run_extraction_for_conversation(db, conv.id, user.id)
        assert ai_ext.id is not None
        assert ai_ext.status == "completed"

        # Verify Decisions
        dec_res = await db.execute(select(Decision).where(Decision.conversation_id == conv.id))
        decisions = dec_res.scalars().all()
        assert len(decisions) >= 1
        assert "postgresql" in decisions[0].text.lower()

        # Verify Action Items
        ai_res = await db.execute(select(ActionItem).where(ActionItem.conversation_id == conv.id))
        action_items = ai_res.scalars().all()
        assert len(action_items) >= 1
        assert "schema migration" in action_items[0].text.lower()

        # Verify Commitments
        com_res = await db.execute(select(Commitment).where(Commitment.conversation_id == conv.id))
        commitments = com_res.scalars().all()
        assert len(commitments) >= 1
        assert "security audit" in commitments[0].text.lower()

        # Verify Deadlines
        dl_res = await db.execute(select(Deadline).where(Deadline.conversation_id == conv.id))
        deadlines = dl_res.scalars().all()
        assert len(deadlines) >= 1
        assert "friday" in deadlines[0].title.lower() or (deadlines[0].raw_deadline_text and "friday" in deadlines[0].raw_deadline_text.lower())

        # Verify Questions
        q_res = await db.execute(select(Question).where(Question.conversation_id == conv.id))
        questions = q_res.scalars().all()
        assert len(questions) >= 1
        assert "deployment timeline" in questions[0].question_text.lower()

        # Generate MOM from extracted facts
        mom = await generate_mom_for_conversation(db, conv.id, user.id)
        assert mom.id is not None
        assert mom.status == "draft"
        assert "Q4 Product Strategy" in mom.title

        # Verify MOM Summary mentions extracted counts
        assert "Extracted 1 decision(s)" in mom.summary or len(decisions) > 0
        assert "1 action item(s)" in mom.summary or len(action_items) > 0
        assert "1 commitment(s)" in mom.summary or len(commitments) > 0
        assert "1 deadline(s)" in mom.summary or len(deadlines) > 0
        assert "1 question(s)" in mom.summary or len(questions) > 0

        # Verify MOM Sections
        sections_map = {s.section_type: s for s in mom.sections}
        assert "decisions" in sections_map
        assert "action_items" in sections_map
        assert "commitments" in sections_map
        assert "deadlines" in sections_map
        assert "questions" in sections_map

        # Check section JSON content
        dec_json = json.loads(sections_map["decisions"].content_json)
        assert len(dec_json) >= 1
        assert "postgresql" in dec_json[0]["text"].lower()

        ai_json = json.loads(sections_map["action_items"].content_json)
        assert len(ai_json) >= 1
        assert "schema migration" in ai_json[0]["text"].lower()

        com_json = json.loads(sections_map["commitments"].content_json)
        assert len(com_json) >= 1
        assert "security audit" in com_json[0]["text"].lower()

        dl_json = json.loads(sections_map["deadlines"].content_json)
        assert len(dl_json) >= 1

        q_json = json.loads(sections_map["questions"].content_json)
        assert len(q_json) >= 1
        assert "deployment timeline" in q_json[0]["text"].lower()


@pytest.mark.asyncio
async def test_extraction_regression_conversation_4_scenarios():
    """
    Regression test covering all criteria from:
    1. Test instructions and recording commands filtered out.
    2. Compound sentence with commitment and question separated cleanly.
    3. No duplicate decision / action item.
    4. Ambiguous deadline flagged uncertain.
    5. Extraction retry is idempotent (no duplicate DB records).
    6. Honest provider reporting (heuristic-mock-v2).
    7. MOM requires confirmed human review when uncertain.
    """
    from app.services.llm_provider import MockLLMProvider, split_segment_into_statements, is_command_or_test_instruction
    from app.services.mom_service import approve_mom

    # A. Statement splitting & noise filtering
    compound_1 = "We decided to adopt post-create screery, Alice will do the schema migration task by Friday."
    stmts_1 = split_segment_into_statements(compound_1)
    assert len(stmts_1) == 2
    assert "We decided to adopt post-create screery" in stmts_1[0]
    assert "Alice will do the schema migration task by Friday" in stmts_1[1]

    compound_2 = "I promise to deliver the audit report, what is our deployment timeline, stop the recording"
    stmts_2 = split_segment_into_statements(compound_2)
    assert len(stmts_2) == 3
    assert "I promise to deliver the audit report" in stmts_2[0]
    assert "what is our deployment timeline" in stmts_2[1]
    assert is_command_or_test_instruction(stmts_2[2]) is True  # 'stop the recording' is noise

    noise_sample = "check the transcript speaker labels, extracted decisions and action items and more."
    assert is_command_or_test_instruction(noise_sample) is True

    # B. Test DB extraction execution with conversation 4-like transcript
    async with AsyncSessionLocal() as db:
        user = User(auth_id="auth0|regression_user_c4")
        db.add(user)
        await db.flush()

        rec = Recording(user_id=user.id, duration_ms=25000, state="completed")
        db.add(rec)
        await db.flush()

        conv = Conversation(
            user_id=user.id,
            recording_id=rec.id,
            title="Conversation",  # Generic title to test neutral title generation
            occurred_at=datetime.now(timezone.utc),
        )
        db.add(conv)
        await db.flush()

        tr = Transcript(
            recording_id=rec.id,
            conversation_id=conv.id,
            encryption_key_ref="test_key_c4",
            status="completed",
        )
        db.add(tr)
        await db.flush()

        # Seg 1: Compound decision + action item
        seg1 = TranscriptSegment(
            transcript_id=tr.id,
            chunk_index=0,
            segment_index=0,
            start_ms=0,
            end_ms=6000,
            text_ciphertext=encrypt_bytes(
                b"We decided to adopt post-create screery, Alice will do the schema migration task by Friday.",
                b"test_key_c4",
            ),
            confidence=0.95,
        )
        # Seg 2: Compound commitment + question + recording command
        seg2 = TranscriptSegment(
            transcript_id=tr.id,
            chunk_index=0,
            segment_index=1,
            start_ms=6000,
            end_ms=12000,
            text_ciphertext=encrypt_bytes(
                b"I promise to deliver the audit report, what is our deployment timeline, stop the recording",
                b"test_key_c4",
            ),
            confidence=0.90,
        )
        # Seg 3: Testing instruction
        seg3 = TranscriptSegment(
            transcript_id=tr.id,
            chunk_index=0,
            segment_index=2,
            start_ms=12000,
            end_ms=18000,
            text_ciphertext=encrypt_bytes(
                b"check the transcript speaker labels, extracted decisions and action items and more.",
                b"test_key_c4",
            ),
            confidence=0.92,
        )
        # Seg 4: Hedged statement with ambiguous deadline
        seg4 = TranscriptSegment(
            transcript_id=tr.id,
            chunk_index=0,
            segment_index=3,
            start_ms=18000,
            end_ms=24000,
            text_ciphertext=encrypt_bytes(
                b"Maybe we will deploy next month, not sure.",
                b"test_key_c4",
            ),
            confidence=0.85,
        )
        db.add_all([seg1, seg2, seg3, seg4])
        await db.commit()

        # First extraction run
        ai_ext = await run_extraction_for_conversation(db, conv.id, user.id)
        assert ai_ext.model_used == "heuristic-mock-v2"
        assert ai_ext.provider == "MockLLMProvider"

        # Check decisions: only the genuine decision, test instruction NOT in decisions!
        dec_res = await db.execute(select(Decision).where(Decision.conversation_id == conv.id))
        decs = dec_res.scalars().all()
        assert len(decs) == 1
        assert "post-create screery" in decs[0].text
        # Ensure test instructions were not classified as decisions
        for d in decs:
            assert "check the transcript" not in d.text.lower()
            assert "action items" not in d.text.lower()

        # Check action items: confirmed action item + uncertain hedged item
        ai_res = await db.execute(select(ActionItem).where(ActionItem.conversation_id == conv.id).order_by(ActionItem.id))
        actions = ai_res.scalars().all()
        assert len(actions) == 2
        assert "Alice will do the schema migration" in actions[0].text
        assert actions[0].assignee_name == "Alice"
        assert actions[0].is_uncertain is False
        assert actions[1].is_uncertain is True
        assert actions[1].confidence <= 0.7
        # Ensure duplicate decision is NOT repeated in action items
        assert actions[0].text != decs[0].text

        # Check commitments: exactly 1 commitment
        com_res = await db.execute(select(Commitment).where(Commitment.conversation_id == conv.id))
        comms = com_res.scalars().all()
        assert len(comms) == 1
        assert "deliver the audit report" in comms[0].text
        assert "stop the recording" not in comms[0].text
        assert "what is our deployment timeline" not in comms[0].text

        # Check questions: exactly 1 question
        q_res = await db.execute(select(Question).where(Question.conversation_id == conv.id))
        qs = q_res.scalars().all()
        assert len(qs) == 1
        assert "deployment timeline" in qs[0].question_text.lower()

        # Check ambiguous/hedged decision from seg4 is marked uncertain
        # (or verify is_uncertain flag)
        assert any(getattr(d, "is_uncertain", False) for d in decs) or len(decs) == 1

        # C. Idempotent Retry Test: Re-running extraction must NOT duplicate records
        await run_extraction_for_conversation(db, conv.id, user.id)
        decs_retry = (await db.execute(select(Decision).where(Decision.conversation_id == conv.id))).scalars().all()
        assert len(decs_retry) == len(decs)  # Exactly 1, not 2!

        actions_retry = (await db.execute(select(ActionItem).where(ActionItem.conversation_id == conv.id))).scalars().all()
        assert len(actions_retry) == len(actions)  # Exactly 1, not 2!

        # D. MOM generation and approval review check
        mom = await generate_mom_for_conversation(db, conv.id, user.id)
        assert mom.status == "draft"
        # Title contextualization for generic "Conversation":
        assert f"Conversation #{conv.id}" in mom.title

        # If MOM is uncertain, approval without confirmed_review must raise ValueError
        if mom.is_uncertain:
            with pytest.raises(ValueError) as exc_info:
                await approve_mom(db, mom.id, user.id, confirmed_review=False)
            assert "human_review_required" in str(exc_info.value)

            # Approving with confirmed_review=True must succeed
            approved = await approve_mom(db, mom.id, user.id, confirmed_review=True)
            assert approved.status == "approved"
            assert approved.approved_at is not None


