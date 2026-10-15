from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.database.session import engine
from app.api.v1.router import router as v1_router


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "message": settings.app_name
    }


@app.get("/health")
async def health():
    async with engine.connect() as connection:
        result = await connection.execute(text("SELECT 1"))

    return {
        "status": "healthy",
        "database": result.scalar() == 1,
        "version": settings.app_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/readiness")
async def readiness():
    db_ready = False
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))
            db_ready = result.scalar() == 1
    except Exception:
        db_ready = False

    return {
        "status": "ready" if db_ready else "not_ready",
        "database": db_ready,
        "version": settings.app_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


app.include_router(
    v1_router,
    prefix="/v1",
)