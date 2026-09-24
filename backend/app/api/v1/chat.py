from __future__ import annotations

"""
Chat endpoint.
POST /api/v1/chat - Routes customer inquiries through the OmniCare AI agent.
POST /api/v1/chat/reset - Resets the authenticated user's conversation session.

Idempotency:
  Clients MAY send an ``Idempotency-Key`` header (opaque string, max 128 chars).
  If present, the server caches the first successful response for that key and
  returns it verbatim for all subsequent requests with the same key within the
  TTL window (default 5 min). This allows frontend clients to safely retry on
  network errors without triggering duplicate LLM calls.

  If the header is omitted, the request is processed normally every time.
  We deliberately do NOT auto-derive a key from (user_id, message) because
  users legitimately ask the same question multiple times in a conversation
  and each request should be processed independently.

  Cached responses are indicated by the ``X-Idempotent-Replayed: true`` header.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Header, Request, Response, status

from app.agent.agent import run_agent, reset_user_session
from app.config import Settings, get_settings
from app.idempotency import get_cached_response, store_response
from app.auth import get_current_user

from app.schemas.models import ChatRequest, ChatResponse, ErrorResponse

logger = logging.getLogger(__name__)

from app.rate_limiter import limiter

router = APIRouter()

# Resolve 422 status constant across Starlette/FastAPI versions without deprecation warnings
STATUS_422 = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Process Chat Interaction",
    description=(
        "Accepts a customer message, routes it through the OmniCare agent "
        "with RAG and tools, and returns the response. "
        "Supports idempotent retries via the optional ``Idempotency-Key`` header."
    ),
    responses={
        status.HTTP_200_OK: {
            "description": (
                "Message processed successfully. Returns the agent response, "
                "policy citations, and tool calls. "
                "Replayed responses include ``X-Idempotent-Replayed: true`` header."
            ),
            "model": ChatResponse,
        },
        STATUS_422: {
            "description": "Validation error: missing or invalid message format.",
            "model": ErrorResponse,
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": (
                "Internal server error occurred during agent reasoning or tool execution."
            ),
            "model": ErrorResponse,
        },
    },
)
@limiter.limit("20/minute")
async def chat(
    request: Request,
    payload: ChatRequest,
    response: Response,
    current_user_id: str = Depends(get_current_user),
    current_settings: Settings = Depends(get_settings),
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        max_length=128,
        description=(
            "Optional client-supplied idempotency key (UUID or opaque string, max 128 chars). "
            "If provided, identical requests within the TTL window return a cached response. "
            "If omitted, the request is processed normally every time."
        ),
    ),
) -> ChatResponse:
    """
    Process a user chat message through the OmniCare AI agent.

    Executes:
    1. Idempotency check -- return cached response if explicit Idempotency-Key was supplied.
    2. Session lookup or initialization for ``current_user_id``.
    3. Model invocation via Google ADK & LiteLLM routing.
    4. Tool execution (Policy RAG, Claim Status, Claim Submission) as needed.
    5. Synthesis of grounded response with citations.
    6. Cache the response under the idempotency key for retry safety (if supplied).

    Returns:
        ChatResponse: Structured payload with agent answer, source citations,
        and tool call traces. Replayed (cached) responses are indicated by
        the ``X-Idempotent-Replayed: true`` header.
    """
    # ── Idempotency check (explicit key only) ──────────────────────────────
    if idempotency_key:
        cached = get_cached_response(idempotency_key)
        if cached is not None:
            response.headers["X-Idempotent-Replayed"] = "true"
            response.headers["X-Idempotency-Key"] = idempotency_key
            return ChatResponse(**cached)

    # ── Execute agent (first call, cache miss, or no key supplied) ─────────
    try:
        result: dict[str, Any] = await run_agent(
            user_id=current_user_id,
            message=payload.message,
        )

        chat_response = ChatResponse(
            response=result["response"],
            sources=result.get("sources", []),
            tool_calls=result.get("tool_calls", []),
        )

        # Cache the successful response for idempotent retries (only if key supplied)
        if idempotency_key:
            store_response(idempotency_key, chat_response.model_dump())
            response.headers["X-Idempotency-Key"] = idempotency_key

        return chat_response

    except HTTPException:
        # Re-raise explicit HTTP exceptions without double-wrapping
        raise

    except Exception as e:
        logger.exception(
            "Unhandled error during chat processing for user '%s': %s",
            current_user_id,
            e,
        )
        # Sanitize internal errors in production; expose details only in development
        error_detail = (
            f"An error occurred while processing your request: {e!s}"
            if current_settings.environment in ("development", "test")
            else (
                "An unexpected error occurred while processing your request. "
                "Please try again later."
            )
        )
        # NOTE: Errors are intentionally NOT cached -- the client should retry on failure.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail,
        ) from e


@router.post(
    "/chat/reset",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reset Chat Session",
    description="Clears the authenticated user's conversation session so the next message starts a fresh context.",
)
@limiter.limit("10/minute")
async def reset_chat(
    request: Request,
    response: Response,
    current_user_id: str = Depends(get_current_user),
) -> Response:
    """
    Reset the conversation session for the authenticated user.

    This clears the ADK InMemorySessionService session so the next message
    from this user starts with a fresh conversation context.
    """
    reset_user_session(current_user_id)
    logger.info("Reset chat session for user '%s'.", current_user_id)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
