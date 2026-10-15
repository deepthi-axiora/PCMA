from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.database.session import get_db
from app.models import User
from app.schemas.transcription import (
    SpeakerRelabelRequest,
    SpeakerResponse,
    TranscriptEditHistoryResponse,
    TranscriptResponse,
    TranscriptSegmentCorrectionRequest,
    TranscriptSegmentResponse,
    TranscriptionStatusResponse,
)
from app.services.recording_service import RecordingError
from app.services.transcription_service import (
    correct_transcript_segment,
    get_segment_edit_history,
    get_transcript,
    get_transcription_status,
    retry_transcription,
)
from app.services.diarization_service import get_diarization_status, relabel_speaker

router = APIRouter(prefix="/recordings", tags=["Transcription"])

_ERROR_MESSAGES = {
    "stt_provider_not_configured": "Speech-to-text is not configured. Contact support or retry after service setup.",
    "supported_language_set_not_configured": "Speech-to-text supported languages are not configured.",
    "unsupported_language": "The detected language is not enabled for this service.",
    "audio_conversion_unavailable": "This audio format is not available for transcription on this server.",
    "audio_too_short": "The recording is shorter than the configured minimum duration.",
    "no_speech_detected": "No speech was detected in the recording.",
}


def _http_error(error: RecordingError) -> HTTPException:
    return HTTPException(status_code=error.status_code,
                         detail={"code": error.code, "message": error.message})


def _status_response(job):
    response = TranscriptionStatusResponse.model_validate(job)
    return response.model_copy(update={
        "last_error_message": _ERROR_MESSAGES.get(job.last_error_code, "Transcription failed; retry the recording." if job.last_error_code else None)
    })


_DIARIZATION_ERROR_MESSAGES = {
    "diarization_provider_not_configured": "Speaker diarization is not configured on this server.",
    "diarization_provider_not_supported": "The configured speaker diarization provider is not supported.",
    "diarization_provider_unavailable": "Speaker diarization is temporarily unavailable.",
    "diarization_provider_request_failed": "The speaker diarization request failed.",
    "diarization_invalid_response": "The speaker diarization service returned invalid results.",
    "diarization_transcript_not_ready": "A completed transcript is required before diarization.",
    "diarization_segments_missing": "Transcript segments are not available for diarization.",
    "diarization_audio_missing": "Recording audio is unavailable for diarization.",
    "diarization_processing_failed": "Speaker diarization could not be completed.",
}


@router.get("/{recording_id}/transcription-status", response_model=TranscriptionStatusResponse)
async def transcription_status(
    recording_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await get_transcription_status(db, recording_id, current_user.id)
    if job is None:
        raise HTTPException(status_code=404, detail="Transcription job not found")
    return _status_response(job)


@router.get("/{recording_id}/transcript", response_model=TranscriptResponse)
async def transcript_detail(
    recording_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await get_transcript(db, recording_id, current_user.id)
    except RecordingError as error:
        raise _http_error(error) from error
    if result is None:
        job = await get_transcription_status(db, recording_id, current_user.id)
        if job is None:
            raise HTTPException(status_code=404, detail="Transcript not found")
        raise HTTPException(
            status_code=409,
            detail={"code": job.last_error_code or "transcription_not_ready",
                    "message": "Transcript is not available yet"},
        )
    return result


@router.post("/{recording_id}/transcription/retry",
             response_model=TranscriptionStatusResponse,
             status_code=status.HTTP_202_ACCEPTED)
async def retry(
    recording_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        job = await retry_transcription(db, recording_id, current_user.id)
        return _status_response(job)
    except RecordingError as error:
        raise _http_error(error) from error


@router.get("/{recording_id}/diarization-status", response_model=TranscriptionStatusResponse)
async def diarization_status(
    recording_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await get_diarization_status(db, recording_id, current_user.id)
    if job is None:
        raise HTTPException(status_code=404, detail="Diarization job not found")
    return TranscriptionStatusResponse.model_validate(job).model_copy(update={
        "last_error_message": _DIARIZATION_ERROR_MESSAGES.get(
            job.last_error_code, "Speaker diarization failed; contact support." if job.last_error_code else None
        ),
    })


@router.patch("/{recording_id}/speakers/{speaker_id}", response_model=SpeakerResponse)
async def update_speaker_label(
    recording_id: int,
    speaker_id: int,
    request: SpeakerRelabelRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await relabel_speaker(db, recording_id, speaker_id, current_user.id,
                                     request.label.strip() if request.label is not None else None,
                                     request.person_id,
                                     replace_person="person_id" in request.model_fields_set)
    except RecordingError as error:
        raise _http_error(error) from error


@router.patch("/{recording_id}/segments/{segment_id}", response_model=TranscriptSegmentResponse)
async def correct_segment(
    recording_id: int,
    segment_id: int,
    request: TranscriptSegmentCorrectionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await correct_transcript_segment(
            db,
            recording_id,
            segment_id,
            current_user.id,
            request.text,
            re_extract=request.re_extract,
        )
    except RecordingError as error:
        raise _http_error(error) from error


@router.get("/{recording_id}/segments/{segment_id}/history", response_model=list[TranscriptEditHistoryResponse])
async def get_segment_history(
    recording_id: int,
    segment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        history = await get_segment_edit_history(db, recording_id, segment_id, current_user.id)
        return [TranscriptEditHistoryResponse.model_validate(h) for h in history]
    except RecordingError as error:
        raise _http_error(error) from error
