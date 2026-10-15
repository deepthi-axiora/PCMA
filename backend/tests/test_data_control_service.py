from datetime import datetime, timezone
import pytest
from sqlalchemy import select

from app.database.session import AsyncSessionLocal
from app.models import AudioFile, AuditEvent, Commitment, Conversation, Recording, User, UserProfile, MOM
from app.services.audio_storage import store_encrypted_audio, read_encrypted_audio
from app.services.data_control_service import (
    delete_user_account,
    delete_user_data,
    export_user_data_package,
)
from app.services.mom_service import generate_mom_for_conversation


@pytest.mark.asyncio
async def test_user_data_export_and_deletion():
    async with AsyncSessionLocal() as db:
        user = User(auth_id="auth0|user_dc_1")
        db.add(user)
        await db.flush()

        profile = UserProfile(user_id=user.id, jurisdiction="US-CA")
        db.add(profile)
        await db.flush()

        rec = Recording(user_id=user.id, duration_ms=10000, state="completed")
        db.add(rec)
        await db.flush()

        # Store physical audio file
        ref = store_encrypted_audio(b"sample audio data for user 1")
        af = AudioFile(
            recording_id=rec.id,
            storage_ref=ref,
            encryption_key_ref="test_key",
            content_type="audio/wav",
            size_bytes=len(b"sample audio data for user 1"),
        )
        db.add(af)

        conv = Conversation(
            user_id=user.id,
            recording_id=rec.id,
            title="Privacy Sync",
            occurred_at=datetime.now(timezone.utc),
        )
        db.add(conv)
        await db.flush()

        mom = await generate_mom_for_conversation(db, conv.id, user.id)

        c = Commitment(
            user_id=user.id,
            conversation_id=conv.id,
            text="Delete data upon request",
            status="open",
            confidence=0.9,
            is_uncertain=False,
            source_segment_ids="[1]",
        )
        db.add(c)
        await db.commit()

        # 1. Test FR-43 User Data Export
        export_pkg = await export_user_data_package(db, user.id)
        assert export_pkg["user"]["id"] == user.id
        assert len(export_pkg["conversations"]) == 1
        assert len(export_pkg["minutes_of_meeting"]) == 1
        assert len(export_pkg["commitments"]) == 1

        # 2. Test FR-42 Data Deletion
        del_result = await delete_user_data(db, user.id)
        assert del_result["status"] == "data_deleted"

        # Verify data purged
        conv_res = await db.execute(select(Conversation).where(Conversation.user_id == user.id))
        assert len(conv_res.scalars().all()) == 0

        mom_res = await db.execute(select(MOM).where(MOM.user_id == user.id))
        assert len(mom_res.scalars().all()) == 0

        af_res = await db.execute(select(AudioFile).where(AudioFile.storage_ref == ref))
        assert af_res.scalar_one_or_none() is None

        # Verify physical audio file deleted
        with pytest.raises(Exception):
            read_encrypted_audio(ref)

        # User profile & account still exist after data deletion
        u_res = await db.execute(select(User).where(User.id == user.id))
        assert u_res.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_audio_deletion_cross_user_safety_and_missing_files():
    async with AsyncSessionLocal() as db:
        user_a = User(auth_id="auth0|user_audio_a")
        user_b = User(auth_id="auth0|user_audio_b")
        db.add_all([user_a, user_b])
        await db.flush()

        rec_a = Recording(user_id=user_a.id, duration_ms=5000, state="completed")
        rec_b = Recording(user_id=user_b.id, duration_ms=5000, state="completed")
        db.add_all([rec_a, rec_b])
        await db.flush()

        ref_a = store_encrypted_audio(b"user A audio")
        ref_b = store_encrypted_audio(b"user B audio")

        af_a = AudioFile(recording_id=rec_a.id, storage_ref=ref_a, encryption_key_ref="k1", content_type="audio/wav", size_bytes=100)
        af_b = AudioFile(recording_id=rec_b.id, storage_ref=ref_b, encryption_key_ref="k2", content_type="audio/wav", size_bytes=100)
        db.add_all([af_a, af_b])
        await db.commit()

        # Purge User A's data
        await delete_user_data(db, user_a.id)

        # User A's physical file must be deleted
        with pytest.raises(Exception):
            read_encrypted_audio(ref_a)

        # User B's physical file must be completely untouched
        assert read_encrypted_audio(ref_b) == b"user B audio"


@pytest.mark.asyncio
async def test_account_deletion_preserves_audit_log_without_pii():
    async with AsyncSessionLocal() as db:
        user = User(auth_id="auth0|user_dc_account_del")
        db.add(user)
        await db.flush()

        profile = UserProfile(user_id=user.id, jurisdiction="EU-GDPR")
        db.add(profile)
        await db.commit()

        user_id = user.id

        # Test FR-44 Account Deletion
        acc_del_res = await delete_user_account(db, user_id)
        assert acc_del_res["status"] == "account_deleted"

        # Verify User & Profile are completely deleted
        u_res = await db.execute(select(User).where(User.id == user_id))
        assert u_res.scalar_one_or_none() is None

        p_res = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
        assert p_res.scalar_one_or_none() is None

        # Verify Audit Event preserved with user_id set to NULL (no PII retained)
        audit_res = await db.execute(
            select(AuditEvent).where(AuditEvent.event_type == "user_account_deleted")
        )
        audit_logs = audit_res.scalars().all()
        assert len(audit_logs) >= 1
        assert audit_logs[0].user_id is None
