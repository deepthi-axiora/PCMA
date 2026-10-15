import json
from datetime import datetime, timezone
import pytest
from sqlalchemy import func, select

from app.database.session import AsyncSessionLocal
from app.models import (
    AuditEvent,
    Conversation,
    Decision,
    ActionItem,
    MOM,
    Recording,
    Transcript,
    TranscriptSegment,
    TranscriptEditHistory,
    User,
)
from app.services.encryption import encrypt_bytes, decrypt_bytes
from app.services.mom_service import generate_mom_for_conversation, approve_mom
from app.services.recording_service import RecordingError
from app.services.transcription_service import (
    correct_transcript_segment,
    get_segment_edit_history,
)


@pytest.mark.asyncio
async def test_transcript_segment_correction_and_audit_history():
    async with AsyncSessionLocal() as db:
        user = User(auth_id="auth0|user_audit_test_1")
        db.add(user)
        await db.flush()

        rec = Recording(user_id=user.id, duration_ms=10000, state="completed")
        db.add(rec)
        await db.flush()

        conv = Conversation(
            user_id=user.id,
            recording_id=rec.id,
            title="Correction Test Conv",
            occurred_at=datetime.now(timezone.utc),
        )
        db.add(conv)
        await db.flush()

        tr = Transcript(
            recording_id=rec.id,
            conversation_id=conv.id,
            encryption_key_ref="test_key_audit",
            status="complete",
        )
        db.add(tr)
        await db.flush()

        orig_text = "We decided to adopt the new architecture, allies will do the deployment by Friday."
        aad = f"pcma-transcript-{tr.id}-0-0".encode()
        seg = TranscriptSegment(
            transcript_id=tr.id,
            chunk_index=0,
            segment_index=0,
            start_ms=100,
            end_ms=5000,
            text_ciphertext=encrypt_bytes(orig_text.encode("utf-8"), aad),
            confidence=0.73,
            low_confidence=False,
        )
        db.add(seg)
        await db.commit()

        # Perform correction without re-extraction
        new_text = "We decided to adopt the new architecture, Alice will do the deployment by Friday."
        res = await correct_transcript_segment(
            db,
            recording_id=rec.id,
            segment_id=seg.id,
            user_id=user.id,
            new_text=new_text,
            re_extract=False,
        )

        assert res["id"] == seg.id
        assert res["text"] == new_text

        # Verify database segment ciphertext is updated with new text
        db_seg = (await db.execute(
            select(TranscriptSegment).where(TranscriptSegment.id == seg.id)
        )).scalar_one()
        decrypted = decrypt_bytes(db_seg.text_ciphertext, aad).decode("utf-8")
        assert decrypted == new_text

        # Verify audit history is preserved in TranscriptEditHistory
        history = await get_segment_edit_history(db, rec.id, seg.id, user.id)
        assert len(history) == 1
        assert history[0].old_text == orig_text
        assert history[0].new_text == new_text
        assert history[0].user_id == user.id

        # Verify AuditEvent was logged
        audit_res = await db.execute(
            select(AuditEvent).where(
                AuditEvent.user_id == user.id,
                AuditEvent.event_type == "transcript_segment_edited",
                AuditEvent.entity_id == rec.id,
            )
        )
        audit_events = list(audit_res.scalars().all())
        assert len(audit_events) >= 1
        meta = json.loads(audit_events[-1].metadata_json)
        assert meta["segment_id"] == seg.id
        assert meta["old_text"] == orig_text
        assert meta["new_text"] == new_text


@pytest.mark.asyncio
async def test_re_extract_confirmation_and_draft_mom_refresh():
    async with AsyncSessionLocal() as db:
        user = User(auth_id="auth0|user_reextract_test_2")
        db.add(user)
        await db.flush()

        rec = Recording(user_id=user.id, duration_ms=12000, state="completed")
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

        tr = Transcript(
            recording_id=rec.id,
            conversation_id=conv.id,
            encryption_key_ref="test_key_reextract",
            status="complete",
        )
        db.add(tr)
        await db.flush()

        aad = f"pcma-transcript-{tr.id}-0-0".encode()
        seg = TranscriptSegment(
            transcript_id=tr.id,
            chunk_index=0,
            segment_index=0,
            start_ms=0,
            end_ms=4000,
            text_ciphertext=encrypt_bytes(
                b"We decided to adopt the new architecture, allies will do the deployment by Friday.",
                aad,
            ),
            confidence=0.73,
            low_confidence=False,
        )
        db.add(seg)
        await db.commit()

        # Step 1: Initial extraction and initial draft MOM
        from app.services.extraction_service import run_extraction_for_conversation

        await run_extraction_for_conversation(db, conv.id, user.id)
        initial_mom = await generate_mom_for_conversation(db, conv.id, user.id)
        assert initial_mom.status == "draft"
        initial_mom_id = initial_mom.id

        # Step 2: User corrects transcript text WITHOUT re-extraction
        corrected_text = "We decided to adopt the new architecture, Alice will do the deployment by Friday."
        await correct_transcript_segment(
            db,
            recording_id=rec.id,
            segment_id=seg.id,
            user_id=user.id,
            new_text=corrected_text,
            re_extract=False,
        )

        # Confirm MOM has NOT been refreshed yet (re_extract was False)
        mom_check = (await db.execute(select(MOM).where(MOM.conversation_id == conv.id))).scalar_one()
        assert mom_check.id == initial_mom_id

        # Step 3: User confirms re-extraction (re_extract=True)
        await correct_transcript_segment(
            db,
            recording_id=rec.id,
            segment_id=seg.id,
            user_id=user.id,
            new_text=corrected_text,
            re_extract=True,
        )

        # Verify only ONE MOM exists (no duplicates created)
        moms = list((await db.execute(
            select(MOM).where(MOM.conversation_id == conv.id)
        )).scalars().all())
        assert len(moms) == 1
        assert moms[0].id == initial_mom_id
        assert moms[0].status == "draft"

        # Verify facts were re-extracted with normalized Alice
        action_items = list((await db.execute(
            select(ActionItem).where(ActionItem.conversation_id == conv.id)
        )).scalars().all())
        assert len(action_items) == 1
        assert action_items[0].assignee_name == "Alice"
        assert "Alice will do" in action_items[0].text or "alice will do" in action_items[0].text.lower()

        # Verify existing draft MOM sections were refreshed and show the corrected assignee "Alice"
        from app.models.mom import MOMSection
        mom_sec_res = await db.execute(
            select(MOMSection).where(
                MOMSection.mom_id == initial_mom_id,
                MOMSection.section_type == "action_items",
            )
        )
        ai_section = mom_sec_res.scalar_one()
        sec_items = json.loads(ai_section.content_json)
        assert len(sec_items) >= 1
        assert sec_items[0]["assignee_name"] == "Alice"
        assert "Alice will do" in sec_items[0]["text"]

        # Verify audit history is preserved with original text ("allies")
        history = await get_segment_edit_history(db, rec.id, seg.id, user.id)
        assert len(history) == 1
        assert "allies" in history[0].old_text
        assert "Alice" in history[0].new_text

        # Verify audit event for mom_refreshed was logged
        audit_res = await db.execute(
            select(AuditEvent).where(
                AuditEvent.user_id == user.id,
                AuditEvent.event_type == "mom_refreshed",
                AuditEvent.entity_id == initial_mom_id,
            )
        )
        assert len(list(audit_res.scalars().all())) >= 1


@pytest.mark.asyncio
async def test_never_overwrite_approved_mom():
    async with AsyncSessionLocal() as db:
        user = User(auth_id="auth0|user_approved_mom_guard")
        db.add(user)
        await db.flush()

        rec = Recording(user_id=user.id, duration_ms=10000, state="completed")
        db.add(rec)
        await db.flush()

        conv = Conversation(
            user_id=user.id,
            recording_id=rec.id,
            title="Approved Meeting",
            occurred_at=datetime.now(timezone.utc),
        )
        db.add(conv)
        await db.flush()

        tr = Transcript(
            recording_id=rec.id,
            conversation_id=conv.id,
            encryption_key_ref="test_key_approved",
            status="complete",
        )
        db.add(tr)
        await db.flush()

        aad = f"pcma-transcript-{tr.id}-0-0".encode()
        seg = TranscriptSegment(
            transcript_id=tr.id,
            chunk_index=0,
            segment_index=0,
            start_ms=0,
            end_ms=4000,
            text_ciphertext=encrypt_bytes(b"We decided to launch on Monday.", aad),
            confidence=0.9,
            low_confidence=False,
        )
        db.add(seg)
        await db.commit()

        # Generate MOM and approve it
        mom = await generate_mom_for_conversation(db, conv.id, user.id)
        approved_mom = await approve_mom(db, mom.id, user.id)
        assert approved_mom.status == "approved"
        approved_summary = approved_mom.summary

        # Correct segment with re_extract=True
        await correct_transcript_segment(
            db,
            recording_id=rec.id,
            segment_id=seg.id,
            user_id=user.id,
            new_text="We decided to launch on Tuesday.",
            re_extract=True,
        )

        # Verify approved MOM was NEVER overwritten or reverted to draft
        moms = list((await db.execute(
            select(MOM).where(MOM.conversation_id == conv.id)
        )).scalars().all())
        assert len(moms) == 1
        assert moms[0].status == "approved"
        assert moms[0].summary == approved_summary


@pytest.mark.asyncio
async def test_unauthorized_user_cannot_correct_segment():
    async with AsyncSessionLocal() as db:
        owner = User(auth_id="auth0|owner_user")
        attacker = User(auth_id="auth0|attacker_user")
        db.add_all([owner, attacker])
        await db.flush()

        rec = Recording(user_id=owner.id, duration_ms=5000, state="completed")
        db.add(rec)
        await db.flush()

        tr = Transcript(
            recording_id=rec.id,
            encryption_key_ref="test_key_sec",
            status="complete",
        )
        db.add(tr)
        await db.flush()

        aad = f"pcma-transcript-{tr.id}-0-0".encode()
        seg = TranscriptSegment(
            transcript_id=tr.id,
            chunk_index=0,
            segment_index=0,
            start_ms=0,
            end_ms=2000,
            text_ciphertext=encrypt_bytes(b"Secret speech", aad),
            confidence=0.9,
        )
        db.add(seg)
        await db.commit()

        with pytest.raises(RecordingError) as exc_info:
            await correct_transcript_segment(
                db,
                recording_id=rec.id,
                segment_id=seg.id,
                user_id=attacker.id,
                new_text="Tampered speech",
            )
        assert exc_info.value.code == "recording_not_found"


@pytest.mark.asyncio
async def test_extract_facts_and_draft_mom_refresh_regression():
    async with AsyncSessionLocal() as db:
        user = User(auth_id="auth0|user_extract_sync_test")
        db.add(user)
        await db.flush()

        rec = Recording(user_id=user.id, duration_ms=15000, state="completed")
        db.add(rec)
        await db.flush()

        conv = Conversation(
            user_id=user.id,
            recording_id=rec.id,
            title="Extraction Sync Conv",
            occurred_at=datetime.now(timezone.utc),
        )
        db.add(conv)
        await db.flush()

        tr = Transcript(
            recording_id=rec.id,
            conversation_id=conv.id,
            encryption_key_ref="test_key_sync",
            status="complete",
        )
        db.add(tr)
        await db.flush()

        aad = f"pcma-transcript-{tr.id}-0-0".encode()
        seg = TranscriptSegment(
            transcript_id=tr.id,
            chunk_index=0,
            segment_index=0,
            start_ms=0,
            end_ms=5000,
            text_ciphertext=encrypt_bytes(
                b"We decided to adopt the new architecture, allies will do the deployment by Friday.",
                aad,
            ),
            confidence=0.75,
            low_confidence=False,
        )
        db.add(seg)
        await db.commit()

        # Step 1: Initial extraction and initial draft MOM
        from app.services.extraction_service import run_extraction_for_conversation

        await run_extraction_for_conversation(db, conv.id, user.id)
        draft_mom = await generate_mom_for_conversation(db, conv.id, user.id)
        assert draft_mom.status == "draft"
        mom_id = draft_mom.id

        # Step 2: Segment corrected to Alice without immediate re-extraction
        await correct_transcript_segment(
            db,
            recording_id=rec.id,
            segment_id=seg.id,
            user_id=user.id,
            new_text="We decided to adopt the new architecture, alice will do the deployment by Friday.",
            re_extract=False,
        )

        # Step 3: Conversation extract endpoint is triggered (e.g. user tapped "Re-extract" on Extracted Facts)
        await run_extraction_for_conversation(db, conv.id, user.id)
        # Refresh draft MOM
        refreshed_mom = await generate_mom_for_conversation(db, conv.id, user.id, refresh_draft=True)
        assert refreshed_mom.id == mom_id
        assert refreshed_mom.status == "draft"

        # Step 4: Verify both extracted facts and draft MOM show corrected assignee "Alice"
        action_items = list((await db.execute(
            select(ActionItem).where(ActionItem.conversation_id == conv.id)
        )).scalars().all())
        assert len(action_items) == 1
        assert action_items[0].assignee_name == "Alice"
        assert "Alice will do" in action_items[0].text

        from app.models.mom import MOMSection
        ai_sec = (await db.execute(
            select(MOMSection).where(
                MOMSection.mom_id == mom_id,
                MOMSection.section_type == "action_items",
            )
        )).scalar_one()
        parsed_sec = json.loads(ai_sec.content_json)
        assert len(parsed_sec) == 1
        assert parsed_sec[0]["assignee_name"] == "Alice"
        assert "Alice will do the deployment by Friday" in parsed_sec[0]["text"]

