"""
API v1 package for the OmniCare Financial backend.

Aggregates all version-1 endpoint routers. Importing this package makes
the v1 API available at the ``/api/v1`` prefix via the main FastAPI app.

Endpoints:
  - ``/health``          -- Service health check.
  - ``/chat``            -- Synchronous chat with idempotency.
  - ``/chat/stream``     -- Streaming SSE chat endpoint.
  - ``/conversations``   -- Conversation history management.
  - ``/auth``            -- Authentication (signup/signin/logout).
"""

from app.api.v1.router import router

__all__ = ["router"]
