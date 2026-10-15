import asyncio
import logging

from app.core.config import settings
from app.database.session import AsyncSessionLocal
from app.services.extraction_service import process_next_extraction_job

logger = logging.getLogger("pcma.extraction_worker")


async def run_worker() -> None:
    while True:
        worked = False
        try:
            async with AsyncSessionLocal() as db:
                worked = await process_next_extraction_job(db)
        except Exception:
            logger.error("extraction_worker_iteration_failed")
        if not worked:
            await asyncio.sleep(getattr(settings, "stt_worker_poll_seconds", 2.0))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())
