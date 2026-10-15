import asyncio
import logging
import shutil
import sys
from pathlib import Path

from app.core.config import settings
from app.database.session import AsyncSessionLocal
import app.services.audio_preprocessing as audio_preprocessing
from app.services.transcription_service import process_next_transcription_job

logger = logging.getLogger("pcma.transcription_worker")


def _log_runtime_configuration() -> None:
    configured_ffmpeg = Path(settings.stt_ffmpeg_path)
    resolved_ffmpeg = (
        str(configured_ffmpeg.resolve())
        if configured_ffmpeg.is_file()
        else shutil.which(settings.stt_ffmpeg_path)
    )
    ffmpeg_available = resolved_ffmpeg is not None
    preprocessing_path = Path(audio_preprocessing.__file__).resolve()
    try:
        preprocessing_mtime_ns = preprocessing_path.stat().st_mtime_ns
    except OSError:
        preprocessing_mtime_ns = 0
    logger.info(
        "transcription_worker_runtime python=%s worker_module=%s preprocessing_module=%s "
        "preprocessing_mtime_ns=%d ffmpeg_configured=%s ffmpeg_available=%s ffmpeg_executable=%s "
        "stt_api_key_configured=%s stt_provider_configured=%s stt_model_configured=%s "
        "stt_supported_languages_configured=%s stt_ffmpeg_path_configured=%s",
        sys.executable,
        str(Path(__file__).resolve()),
        str(preprocessing_path),
        preprocessing_mtime_ns,
        bool(settings.stt_ffmpeg_path),
        ffmpeg_available,
        resolved_ffmpeg or "not_found",
        bool(settings.stt_api_key),
        bool(settings.stt_provider),
        bool(settings.stt_model),
        bool(settings.stt_supported_languages.strip()),
        bool(settings.stt_ffmpeg_path),
    )


async def run_worker() -> None:
    _log_runtime_configuration()
    while True:
        worked = False
        try:
            async with AsyncSessionLocal() as db:
                worked = await process_next_transcription_job(db)
        except Exception:
            # Avoid logging provider payloads, transcript text, or audio metadata.
            logger.exception("transcription_worker_iteration_failed")
        if not worked:
            await asyncio.sleep(settings.stt_worker_poll_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())
