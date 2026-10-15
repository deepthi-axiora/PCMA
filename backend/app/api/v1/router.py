from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.models import User
from app.api.v1.profile import router as profile_router
from app.api.v1.recordings import router as recordings_router
from app.api.v1.transcriptions import router as transcriptions_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.moms import router as moms_router
from app.api.v1.sharing_export import router as sharing_export_router
from app.api.v1.memory_search import router as memory_search_router
from app.api.v1.commitments_reminders import router as commitments_reminders_router
from app.api.v1.assistant import router as assistant_router
from app.api.v1.sync_hardening import router as sync_hardening_router
from app.api.v1.data_control import router as data_control_router

router = APIRouter()
router.include_router(profile_router)
router.include_router(recordings_router)
router.include_router(transcriptions_router)
router.include_router(conversations_router)
router.include_router(moms_router)
router.include_router(sharing_export_router)
router.include_router(memory_search_router)
router.include_router(commitments_reminders_router)
router.include_router(assistant_router)
router.include_router(sync_hardening_router)
router.include_router(data_control_router)


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
):
    return {
        "id": current_user.id,
        "auth_id": current_user.auth_id,
        "created_at": current_user.created_at,
    }
