import os

# Keep the suite self-contained: the deployed database is not needed for model
# and service tests. Set these before importing the app's singleton engine.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ.setdefault(
    "AUDIO_ENCRYPTION_KEY",
    "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
)

import pytest_asyncio

from app.database.base import Base
from app.database.session import engine
import app.models  # noqa: F401 — register all ORM tables with Base.metadata

engine.echo = False


@pytest_asyncio.fixture(autouse=True)
async def cleanup_database_engine():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()
