import base64
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import get_current_user
from app.database.session import AsyncSessionLocal, get_db
from app.main import app
from app.models import AuditEvent, AudioFile, User, UserProfile
from app.services.audio_storage import read_encrypted_audio
from app.services.recording_service import start_recording


async def _make_recording():
    async with AsyncSessionLocal() as db:
        user = User(auth_id=f"audio-api-test-{uuid4()}")
        db.add(user)
        await db.flush()
        db.add(UserProfile(user_id=user.id, jurisdiction="IN"))
        await db.commit()
        recording = await start_recording(
            db,
            user.id,
            audio_source="phone_microphone",
            source_available=True,
            microphone_permission_granted=True,
            consent_acknowledged=True,
        )
        return user, recording


async def _request_as(user, method, path, **kwargs):
    async def override_db():
        async with AsyncSessionLocal() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.request(method, path, **kwargs)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def encrypted_audio_storage(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(settings, "audio_storage_dir", str(tmp_path))
    monkeypatch.setattr(
        settings, "audio_encryption_key", base64.urlsafe_b64encode(b"k" * 32).decode()
    )
    return tmp_path


@pytest.mark.asyncio
async def test_upload_audio_multipart_stores_encrypted_file_metadata_and_audit(encrypted_audio_storage):
    user, recording = await _make_recording()
    payload = b"mp3 audio fixture bytes"

    response = await _request_as(
        user,
        "POST",
        f"/v1/recordings/{recording.id}/audio",
        files={"audio": ("meeting.mp3", payload, "audio/mpeg")},
        params={"duration_ms": "1750"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["recording_id"] == recording.id
    assert body["content_type"] == "audio/mpeg"
    assert body["size_bytes"] == len(payload)
    assert body["duration_ms"] == 1750
    async with AsyncSessionLocal() as db:
        audio = (await db.execute(select(AudioFile).where(
            AudioFile.recording_id == recording.id
        ))).scalar_one()
        assert audio.content_type == "audio/mpeg"
        assert audio.size_bytes == len(payload)
        assert audio.duration_ms == 1750
        events = (await db.execute(select(AuditEvent.event_type).where(
            AuditEvent.user_id == user.id
        ))).scalars().all()
        assert "audio.stored" in events
    stored = encrypted_audio_storage / audio.storage_ref
    assert stored.read_bytes() != payload
    assert read_encrypted_audio(audio.storage_ref) == payload


@pytest.mark.asyncio
async def test_upload_audio_rejects_non_audio_multipart_file():
    user, recording = await _make_recording()
    response = await _request_as(
        user,
        "POST",
        f"/v1/recordings/{recording.id}/audio",
        files={"audio": ("notes.txt", b"not audio", "text/plain")},
    )
    assert response.status_code == 415


@pytest.mark.asyncio
async def test_upload_audio_rejects_empty_file():
    user, recording = await _make_recording()
    response = await _request_as(
        user,
        "POST",
        f"/v1/recordings/{recording.id}/audio",
        files={"audio": ("empty.mp3", b"", "audio/mpeg")},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "empty_audio"


@pytest.mark.asyncio
async def test_upload_audio_is_scoped_to_recording_owner():
    owner, recording = await _make_recording()
    other, _ = await _make_recording()
    response = await _request_as(
        other,
        "POST",
        f"/v1/recordings/{recording.id}/audio",
        files={"audio": ("meeting.mp3", b"audio", "audio/mpeg")},
    )
    assert response.status_code == 404
    async with AsyncSessionLocal() as db:
        assert (await db.execute(select(AudioFile).where(
            AudioFile.recording_id == recording.id
        ))).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_upload_audio_reports_storage_configuration_failure(monkeypatch):
    user, recording = await _make_recording()

    def fail_storage(_content):
        from app.services.audio_storage import AudioStorageNotConfigured

        raise AudioStorageNotConfigured("Audio encryption is not configured")

    monkeypatch.setattr("app.services.recording_service.store_encrypted_audio", fail_storage)
    response = await _request_as(
        user,
        "POST",
        f"/v1/recordings/{recording.id}/audio",
        files={"audio": ("meeting.mp3", b"audio", "audio/mpeg")},
    )
    assert response.status_code == 503


def test_audio_upload_openapi_uses_multipart_file_control():
    operation = app.openapi()["paths"]["/v1/recordings/{recording_id}/audio"]["post"]
    request_body = operation["requestBody"]["content"]
    assert "application/json" not in request_body
    schema = request_body["multipart/form-data"]["schema"]
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        schema = app.openapi()["components"]["schemas"][name]
    audio_schema = schema["properties"]["audio"]
    # OpenAPI 3.1 represents UploadFile as a string with contentMediaType;
    # OpenAPI 3.0 represents the same file field as format=binary.
    assert audio_schema.get("format") == "binary" or audio_schema.get("contentMediaType")
    assert any(
        parameter["name"] == "duration_ms" and parameter["in"] == "query"
        for parameter in operation["parameters"]
    )


@pytest.mark.asyncio
async def test_recording_recovery_and_discard_api_endpoints():
    user, recording = await _make_recording()

    # GET /v1/recordings/active returns the open recording
    active_resp = await _request_as(user, "GET", "/v1/recordings/active")
    assert active_resp.status_code == 200
    assert active_resp.json()["id"] == recording.id
    assert active_resp.json()["state"] == "active"

    # Attempting to recover empty session returns 400 with clear message to discard
    recover_empty = await _request_as(user, "POST", f"/v1/recordings/{recording.id}/recover")
    assert recover_empty.status_code == 400
    data = recover_empty.json()["detail"]
    assert data["code"] == "no_audio_to_recover"
    assert "Discard" in data["message"]

    # Session is still active on server, not falsely recovered
    active_resp_still = await _request_as(user, "GET", "/v1/recordings/active")
    assert active_resp_still.status_code == 200
    assert active_resp_still.json()["id"] == recording.id

    # Another user cannot discard or recover this session (404 scoped)
    other_user = User(auth_id=f"other-user-{uuid4()}")
    async with AsyncSessionLocal() as db:
        db.add(other_user)
        await db.commit()
    cross_discard = await _request_as(other_user, "POST", f"/v1/recordings/{recording.id}/cancel")
    assert cross_discard.status_code == 404

    # Discard active recording via POST /v1/recordings/{id}/cancel
    discard_resp = await _request_as(user, "POST", f"/v1/recordings/{recording.id}/cancel")
    assert discard_resp.status_code == 200
    assert discard_resp.json()["id"] == recording.id
    assert discard_resp.json()["state"] == "failed"

    # Repeating discard on already-cancelled session is idempotent 200
    repeat_discard = await _request_as(user, "POST", f"/v1/recordings/{recording.id}/cancel")
    assert repeat_discard.status_code == 200
    assert repeat_discard.json()["state"] == "failed"

    # GET /v1/recordings/active now returns 404
    active_resp_after = await _request_as(user, "GET", "/v1/recordings/active")
    assert active_resp_after.status_code == 404

    # User can start a new recording via POST /v1/recordings
    start_resp = await _request_as(
        user,
        "POST",
        "/v1/recordings",
        json={
            "audio_source": "phone_microphone",
            "source_available": True,
            "microphone_permission_granted": True,
            "consent_acknowledged": True,
        },
    )
    assert start_resp.status_code == 201
    new_rec_id = start_resp.json()["id"]
    assert new_rec_id != recording.id
    assert start_resp.json()["state"] == "active"

    # Upload audio to new recording and test Recover with audio
    wav_payload = b"RIFFmockwavcontent"
    upload_resp = await _request_as(
        user,
        "POST",
        f"/v1/recordings/{new_rec_id}/audio",
        files={"audio": ("test.wav", wav_payload, "audio/wav")},
    )
    assert upload_resp.status_code == 201

    # Recovering session with audio finalizes it into processing
    recover_audio = await _request_as(user, "POST", f"/v1/recordings/{new_rec_id}/recover")
    assert recover_audio.status_code == 200
    assert recover_audio.json()["id"] == new_rec_id
    assert recover_audio.json()["state"] == "processing"

    # Repeating recover on already-processing session is idempotent 200
    repeat_recover = await _request_as(user, "POST", f"/v1/recordings/{new_rec_id}/recover")
    assert repeat_recover.status_code == 200
    assert repeat_recover.json()["state"] == "processing"


