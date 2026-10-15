from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.database.session import get_db
from app.models import User
from app.schemas.recording import (
    AudioFileResponse,
    AudioSourceChange,
    RecordingResponse,
    RecordingStart,
)
from app.services.audio_storage import AudioStorageNotConfigured, read_encrypted_audio
from app.services.recording_service import (
    RecordingError,
    cancel_recording,
    change_audio_source,
    get_active_recording,
    get_audio_file,
    get_recording,
    list_recordings,
    pause_recording,
    recover_active_recording,
    resume_recording,
    start_recording,
    stop_recording,
    upload_audio,
)

router = APIRouter(prefix="/recordings", tags=["Recordings"])


def _http_error(error: RecordingError) -> HTTPException:
    return HTTPException(status_code=error.status_code,
                         detail={"code": error.code, "message": error.message})


@router.post("", response_model=RecordingResponse, status_code=status.HTTP_201_CREATED)
async def create_recording(
    data: RecordingStart,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await start_recording(
            db, current_user.id,
            audio_source=data.audio_source,
            source_available=data.source_available,
            microphone_permission_granted=data.microphone_permission_granted,
            consent_acknowledged=data.consent_acknowledged,
        )
    except RecordingError as error:
        raise _http_error(error) from error


@router.get("", response_model=list[RecordingResponse])
async def get_recordings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_recordings(db, current_user.id)


@router.get("/active", response_model=RecordingResponse)
async def get_active(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    recording = await get_active_recording(db, current_user.id)
    if recording is None:
        raise HTTPException(status_code=404, detail="No active recording")
    return recording


@router.post("/recover-active", response_model=RecordingResponse)
async def recover_active(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await recover_active_recording(db, current_user.id)
    except RecordingError as error:
        raise _http_error(error) from error


@router.post("/cancel-active", response_model=RecordingResponse)
async def cancel_active(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    recording = await get_active_recording(db, current_user.id)
    if recording is None:
        raise HTTPException(status_code=404, detail="No active recording")
    try:
        return await cancel_recording(db, recording.id, current_user.id, reason="user_discard")
    except RecordingError as error:
        raise _http_error(error) from error




@router.get("/{recording_id}", response_model=RecordingResponse)
async def get_recording_detail(
    recording_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    recording = await get_recording(db, recording_id, current_user.id)
    if recording is None:
        raise HTTPException(status_code=404, detail="Recording not found")
    return recording


@router.post("/{recording_id}/audio", response_model=AudioFileResponse,
             status_code=status.HTTP_201_CREATED)
async def upload_recording_audio(
    recording_id: int,
    audio: UploadFile = File(..., description="Audio file to attach to this recording"),
    duration_ms: int | None = Query(default=None, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content_type = audio.content_type or "application/octet-stream"
    if not (content_type.startswith("audio/") or content_type == "application/octet-stream"):
        raise HTTPException(status_code=415, detail="Upload must contain audio")
    try:
        content = await audio.read()
        return await upload_audio(db, recording_id, current_user.id,
                                  content, content_type, duration_ms)
    except RecordingError as error:
        raise _http_error(error) from error
    except AudioStorageNotConfigured as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    finally:
        await audio.close()


@router.get("/{recording_id}/audio")
async def download_recording_audio(
    recording_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    audio = await get_audio_file(db, recording_id, current_user.id)
    if audio is None:
        raise HTTPException(status_code=404, detail="Audio not found")
    try:
        content = read_encrypted_audio(audio.storage_ref)
    except AudioStorageNotConfigured as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=500, detail="Stored audio could not be read") from error
    return Response(content=content, media_type=audio.content_type,
                    headers={"Content-Length": str(len(content))})


@router.post("/{recording_id}/pause", response_model=RecordingResponse)
async def pause(
    recording_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await pause_recording(db, recording_id, current_user.id)
    except RecordingError as error:
        raise _http_error(error) from error


@router.post("/{recording_id}/resume", response_model=RecordingResponse)
async def resume(
    recording_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await resume_recording(db, recording_id, current_user.id)
    except RecordingError as error:
        raise _http_error(error) from error


@router.post("/{recording_id}/stop", response_model=RecordingResponse)
async def stop(
    recording_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await stop_recording(db, recording_id, current_user.id)
    except RecordingError as error:
        raise _http_error(error) from error


@router.patch("/{recording_id}/audio-source", response_model=RecordingResponse)
async def set_audio_source(
    recording_id: int,
    data: AudioSourceChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await change_audio_source(db, recording_id, current_user.id,
                                         data.audio_source, data.source_available)
    except RecordingError as error:
        raise _http_error(error) from error


@router.post("/{recording_id}/cancel", response_model=RecordingResponse)
async def cancel(
    recording_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await cancel_recording(db, recording_id, current_user.id)
    except RecordingError as error:
        raise _http_error(error) from error


@router.post("/{recording_id}/recover", response_model=RecordingResponse)
async def recover(
    recording_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await recover_active_recording(db, current_user.id, recording_id)
    except RecordingError as error:
        raise _http_error(error) from error

