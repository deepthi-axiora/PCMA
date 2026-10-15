import asyncio
import argparse
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.session import AsyncSessionLocal
from app.models import Recording
from app.services.transcription_service import retry_transcription
from sqlalchemy import select


async def run_retry(recording_id: int, require_error_code: str | None):
    async with AsyncSessionLocal() as db:
        recording = (await db.execute(
            select(Recording).where(Recording.id == recording_id)
        )).scalar_one_or_none()
        if not recording:
            print(f"Error: Recording ID {recording_id} not found.")
            sys.exit(1)

        job = await retry_transcription(
            db,
            recording_id=recording_id,
            user_id=recording.user_id,
            require_error_code=require_error_code,
        )
        print(f"Successfully retried transcription job {job.id} for recording {recording_id}:")
        print(f"  Status        : {job.status}")
        print(f"  Provider      : {job.provider}")
        print(f"  Attempts      : {job.attempts}")
        print(f"  Available At  : {job.available_at}")


def main():
    parser = argparse.ArgumentParser(description="Safely retry an eligible failed transcription job.")
    parser.add_argument("recording_id", type=int, help="The ID of the recording to retry transcription for")
    parser.add_argument(
        "--require-error-code",
        type=str,
        default="stt_provider_not_supported",
        help="Only retry if last_error_code matches (default: 'stt_provider_not_supported')",
    )
    args = parser.parse_args()

    asyncio.run(run_retry(args.recording_id, args.require_error_code))


if __name__ == "__main__":
    main()
