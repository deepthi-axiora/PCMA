from datetime import datetime, timezone
import httpx
import pytest

from app.core.security import get_current_user
from app.database.session import AsyncSessionLocal
from app.main import app
from app.models import Conversation, Decision, Recording, Transcript, TranscriptSegment, User
from app.services.encryption import encrypt_bytes


async def _create_test_user(auth_id: str) -> User:
    async with AsyncSessionLocal() as db:
        user = User(auth_id=auth_id)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def _create_test_conversation(user_id: int, title: str, occurred_at: datetime) -> Conversation:
    async with AsyncSessionLocal() as db:
        rec = Recording(
            user_id=user_id,
            state="ready_for_review",
            status="ready_for_review",
            audio_source="phone_microphone",
            started_at=occurred_at,
            created_at=occurred_at,
        )
        db.add(rec)
        await db.flush()

        conv = Conversation(
            user_id=user_id,
            recording_id=rec.id,
            title=title,
            occurred_at=occurred_at,
            created_at=occurred_at,
        )
        db.add(conv)
        await db.flush()

        tr = Transcript(
            recording_id=rec.id,
            conversation_id=conv.id,
            encryption_key_ref=f"pcma-transcript-{conv.id}-0-0",
            language="en",
            status="completed",
        )
        db.add(tr)
        await db.flush()

        key_ref = f"pcma-transcript-{tr.id}-0-0".encode()
        seg = TranscriptSegment(
            transcript_id=tr.id,
            chunk_index=0,
            segment_index=0,
            start_ms=0,
            end_ms=5000,
            text_ciphertext=encrypt_bytes(b"We discussed project milestones and agreed on deadlines.", key_ref),
            confidence=0.95,
        )
        db.add(seg)

        await db.commit()
        await db.refresh(conv)
        return conv


@pytest.mark.asyncio
async def test_list_conversations_user_scoping_and_ordering():
    user1 = await _create_test_user("auth0|user_conv_1")
    user2 = await _create_test_user("auth0|user_conv_2")

    t1 = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)

    conv1 = await _create_test_conversation(user1.id, "User 1 Early", t1)
    conv2 = await _create_test_conversation(user1.id, "User 1 Late", t2)
    _conv_other = await _create_test_conversation(user2.id, "User 2 Conv", t2)

    # User 1 request
    app.dependency_overrides[get_current_user] = lambda: user1
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res1 = await client.get("/v1/conversations")
        assert res1.status_code == 200
        data1 = res1.json()
        assert len(data1) == 2
        # Ordered newest first (Late then Early)
        assert data1[0]["id"] == conv2.id
        assert data1[0]["title"] == "User 1 Late"
        assert data1[0]["status"] == "ready_for_review"
        assert data1[1]["id"] == conv1.id

    # User 2 request
    app.dependency_overrides[get_current_user] = lambda: user2
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res2 = await client.get("/v1/conversations")
        assert res2.status_code == 200
        data2 = res2.json()
        assert len(data2) == 1
        assert data2[0]["title"] == "User 2 Conv"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_conversation_detail_and_isolation():
    user1 = await _create_test_user("auth0|user_detail_1")
    user2 = await _create_test_user("auth0|user_detail_2")

    now = datetime.now(timezone.utc)
    conv1 = await _create_test_conversation(user1.id, "Detail Test", now)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Owner access succeeds
        app.dependency_overrides[get_current_user] = lambda: user1
        res1 = await client.get(f"/v1/conversations/{conv1.id}")
        assert res1.status_code == 200
        data = res1.json()
        assert data["id"] == conv1.id
        assert data["recording_id"] == conv1.recording_id
        assert data["status"] == "ready_for_review"

        # Non-owner access gets 404
        app.dependency_overrides[get_current_user] = lambda: user2
        res2 = await client.get(f"/v1/conversations/{conv1.id}")
        assert res2.status_code == 404

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_process_extraction_endpoint_alias():
    user1 = await _create_test_user("auth0|user_extract_alias")
    now = datetime.now(timezone.utc)
    conv = await _create_test_conversation(user1.id, "Extraction Alias Test", now)

    app.dependency_overrides[get_current_user] = lambda: user1
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(f"/v1/conversations/{conv.id}/process-extraction")
        assert res.status_code == 200
        data = res.json()
        assert data["conversation_id"] == conv.id

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_recording_id_15_resolves_to_conversation_id_5_and_mom_api():
    user = await _create_test_user("auth0|rec15_conv5_api")
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        rec = Recording(
            id=15,
            user_id=user.id,
            state="ready_for_review",
            status="ready_for_review",
            audio_source="phone_microphone",
            started_at=now,
            created_at=now,
        )
        db.add(rec)
        await db.flush()

        conv = Conversation(
            id=5,
            user_id=user.id,
            recording_id=15,
            title="Meeting 15 to 5",
            occurred_at=now,
            created_at=now,
        )
        db.add(conv)
        await db.flush()

        dec = Decision(
            user_id=user.id,
            conversation_id=5,
            text="Agreed on schedule",
            confidence=0.98,
        )
        db.add(dec)
        await db.commit()

    app.dependency_overrides[get_current_user] = lambda: user
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Detail endpoint using recording ID 15 resolves to Conversation ID 5
        res_detail = await client.get("/v1/conversations/15")
        assert res_detail.status_code == 200
        detail_data = res_detail.json()
        assert detail_data["id"] == 5
        assert detail_data["recording_id"] == 15

        # 2. MOM generation using recording ID 15 resolves and generates for Conversation ID 5
        res_gen = await client.post("/v1/conversations/15/mom/generate")
        assert res_gen.status_code == 201
        gen_data = res_gen.json()
        assert gen_data["conversation_id"] == 5

        # 3. MOM retrieval using recording ID 15 resolves to MOM for Conversation ID 5
        res_mom_rec = await client.get("/v1/conversations/15/mom")
        assert res_mom_rec.status_code == 200
        assert res_mom_rec.json()["conversation_id"] == 5

        # 4. MOM retrieval using Conversation ID 5 returns the exact same MOM
        res_mom_conv = await client.get("/v1/conversations/5/mom")
        assert res_mom_conv.status_code == 200
        assert res_mom_conv.json()["id"] == gen_data["id"]
        assert res_mom_conv.json()["conversation_id"] == 5

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_overlapping_ids_api_prefers_exact_conversation():
    user = await _create_test_user("auth0|overlap_api")
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        rec1 = Recording(id=800, user_id=user.id, state="completed")
        rec2 = Recording(id=900, user_id=user.id, state="completed")
        db.add_all([rec1, rec2])
        await db.flush()

        conv1 = Conversation(
            id=900,
            user_id=user.id,
            recording_id=800,
            title="Conv 1 (id 900)",
            occurred_at=now,
        )
        conv2 = Conversation(
            id=1000,
            user_id=user.id,
            recording_id=900,  # overlaps with conv1.id
            title="Conv 2 (recording 900)",
            occurred_at=now,
        )
        db.add_all([conv1, conv2])
        await db.flush()

        dec1 = Decision(user_id=user.id, conversation_id=900, text="Dec 1", confidence=1.0)
        dec2 = Decision(user_id=user.id, conversation_id=1000, text="Dec 2", confidence=1.0)
        db.add_all([dec1, dec2])
        await db.commit()

    app.dependency_overrides[get_current_user] = lambda: user
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Requesting ID 900 must return conv1 (id: 900, recording_id: 800), NOT conv2 (recording_id: 900)
        res_detail = await client.get("/v1/conversations/900")
        assert res_detail.status_code == 200
        assert res_detail.json()["id"] == 900
        assert res_detail.json()["recording_id"] == 800

        # MOM generation on 900 must generate for conv1 (id: 900)
        res_gen = await client.post("/v1/conversations/900/mom/generate")
        assert res_gen.status_code == 201
        assert res_gen.json()["conversation_id"] == 900

        # MOM retrieval on 900 must return MOM for conv1 (id: 900)
        res_mom = await client.get("/v1/conversations/900/mom")
        assert res_mom.status_code == 200
        assert res_mom.json()["conversation_id"] == 900

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_nonexistent_and_ownership_checks_api():
    user_owner = await _create_test_user("auth0|owner_api_user")
    user_other = await _create_test_user("auth0|other_api_user")
    now = datetime.now(timezone.utc)
    conv = await _create_test_conversation(user_owner.id, "Owner Secret Meeting", now)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Nonexistent conversation returns 404
        app.dependency_overrides[get_current_user] = lambda: user_owner
        res_nonexistent = await client.get("/v1/conversations/999999")
        assert res_nonexistent.status_code == 404

        res_nonexistent_mom = await client.get("/v1/conversations/999999/mom")
        assert res_nonexistent_mom.status_code == 404

        res_nonexistent_gen = await client.post("/v1/conversations/999999/mom/generate")
        assert res_nonexistent_gen.status_code == 404

        # 2. Ownership check prevents other user from accessing owner's conversation
        app.dependency_overrides[get_current_user] = lambda: user_other

        # By conversation ID
        res_other_conv = await client.get(f"/v1/conversations/{conv.id}")
        assert res_other_conv.status_code == 404

        # By recording ID fallback
        res_other_rec = await client.get(f"/v1/conversations/{conv.recording_id}")
        assert res_other_rec.status_code == 404

        # MOM operations
        res_other_mom = await client.get(f"/v1/conversations/{conv.id}/mom")
        assert res_other_mom.status_code == 404

        res_other_gen = await client.post(f"/v1/conversations/{conv.id}/mom/generate")
        assert res_other_gen.status_code == 404

    app.dependency_overrides.clear()

