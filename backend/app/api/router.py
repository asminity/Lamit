from fastapi import APIRouter

from backend.app.api.auth import router as auth_router
from backend.app.api.threads import router as threads_router
from backend.app.api.history import router as history_router
from backend.app.api.chat import router as chat_router
from backend.app.api.memories import router as memories_router

api_router = APIRouter(prefix="/api")

api_router.include_router(auth_router)
api_router.include_router(threads_router)
api_router.include_router(history_router)
api_router.include_router(chat_router)
api_router.include_router(memories_router)

