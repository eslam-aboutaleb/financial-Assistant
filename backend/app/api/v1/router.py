"""
API v1 Router - mounts all v1 endpoint routers.
"""

from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.chat import router as chat_router
from app.api.v1.auth import router as auth_router

router = APIRouter(prefix="/api/v1")

router.include_router(health_router, tags=["Health"])
router.include_router(chat_router, tags=["Chat"])
router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
