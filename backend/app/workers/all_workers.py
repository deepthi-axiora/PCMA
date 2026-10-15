import asyncio
import logging

from app.workers.transcription_worker import run_worker as run_transcription
from app.workers.diarization_worker import run_worker as run_diarization
from app.workers.extraction_worker import run_worker as run_extraction
from app.workers.reminder_worker import run_worker as run_reminder

logger = logging.getLogger("pcma.all_workers")


async def run_all_workers() -> None:
    logger.info("Starting all PCMA background workers (transcription, diarization, extraction, reminder)...")
    await asyncio.gather(
        run_transcription(),
        run_diarization(),
        run_extraction(),
        run_reminder(),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    try:
        asyncio.run(run_all_workers())
    except (KeyboardInterrupt, SystemExit):
        logger.info("PCMA background workers stopped.")
