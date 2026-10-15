import asyncio
import logging

from app.core.config import settings
from app.database.session import AsyncSessionLocal
from app.services.commitment_reminder_service import process_due_reminders

logger = logging.getLogger("pcma.reminder_worker")


async def run_worker() -> None:
    while True:
        try:
            async with AsyncSessionLocal() as db:
                count = await process_due_reminders(db)
                if count > 0:
                    logger.info("reminder_worker_dispatched reminders_count=%d", count)
        except Exception:
            logger.error("reminder_worker_iteration_failed")
        await asyncio.sleep(getattr(settings, "stt_worker_poll_seconds", 2.0))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())
