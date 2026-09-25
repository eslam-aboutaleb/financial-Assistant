"""
API v1 Router - mounts all v1 endpoint routers under the /api/v1 prefix.

This router acts as the single aggregation point for all version-1 API
endpoints. Each sub-router is responsible for its own domain:

  - ``/health``        -- Service health and dependency checks.
  - ``/chat``          -- Synchronous chat endpoint with idempotency.
  - ``/chat/stream``   -- Streaming SSE chat endpoint.
  - ``/conversations`` -- Conversation history CRUD operations.
  - ``/auth``          -- Public authentication endpoints (signup/signin/logout).

Including this router in ``app/main.py`` makes all v1 endpoints available
at their documented paths without requiring individual route registrations.
"""

from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.api.v1.chat import router as chat_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.chat_stream import router as chat_stream_router
from app.api.v1.auth import router as auth_router

router = APIRouter(prefix="/api/v1")

router.include_router(health_router, tags=["Health"])
router.include_router(chat_router, tags=["Chat"])
router.include_router(conversations_router, tags=["Conversations"])
router.include_router(chat_stream_router, tags=["Chat"])
router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
