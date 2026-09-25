
"""
Chat endpoint.

POST /api/v1/chat - Routes customer inquiries through the OmniCare AI agent.
POST /api/v1/chat/reset - Resets the authenticated user's conversation session.
GET  /api/v1/chat/conversations - Lists the user's past conversations.
GET  /api/v1/chat/conversations/{id} - Retrieves a single conversation history.

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
import litellm

from app.agent.agent import run_agent, reset_user_session
from app.config import Settings, get_settings
from app.idempotency import store_response, idempotent_endpoint
from app.auth import get_current_user
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.models.conversation import Conversation
import uuid

from app.schemas.models import (
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    ConversationListResponse,
    ConversationDetailResponse,
)

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
@idempotent_endpoint()
async def chat(
    payload: ChatRequest,
    request: Request,
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
    """Process a user chat message through the OmniCare AI agent.

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
    if payload.user_id and payload.user_id != current_user_id:
        logger.warning(
            "Request body user_id '%s' differs from authenticated user '%s'; using authenticated user.",
            payload.user_id,
            current_user_id,
        )
        effective_user_id = current_user_id
    else:
        effective_user_id = payload.user_id or current_user_id

    try:
        result: dict[str, Any] = await run_agent(
            user_id=effective_user_id,
            message=payload.message,
        )
    except litellm.BadRequestError as exc:
        message_text = str(exc)
        if "tool_call_id" in message_text or "tool_calls" in message_text:
            logger.warning(
                "Detected bad tool-call history for user '%s'; resetting session and retrying once.",
                effective_user_id,
            )
            reset_user_session(effective_user_id)
            result = await run_agent(
                user_id=effective_user_id,
                message=payload.message,
            )
        else:
            raise
    except HTTPException:
        # Re-raise explicit HTTP exceptions without double-wrapping
        raise
    except Exception as e:
        logger.exception(
            "Unhandled error during chat processing for user '%s': %s",
            current_user_id,
            e,
        )
        # Always return a generic, user-friendly error message.
        # Internal details are logged server-side only.
        error_detail = (
            "An unexpected error occurred while processing your request. "
            "Please try again later."
        )
        # NOTE: Errors are intentionally NOT cached -- the client should retry on failure.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail,
        ) from e

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


@router.post(
    "/chat/reset",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reset Chat Session",
    description=(
        "Clears the authenticated user's conversation session "
        "so the next message starts a fresh context."
    ),
)
@limiter.limit("10/minute")
async def reset_chat(
    request: Request,
    response: Response,
    current_user_id: str = Depends(get_current_user),
) -> Response:
    """Reset the conversation session for the authenticated user.

    This clears the ADK InMemorySessionService session so the next message
    from this user starts with a fresh conversation context.
    """
    reset_user_session(current_user_id)
    logger.info("Reset chat session for user '%s'.", current_user_id)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get(
    "/chat/conversations",
    response_model=ConversationListResponse,
    summary="List Conversations",
    description=(
        "Returns metadata for all conversations belonging to the authenticated user."
    ),
)
async def list_conversations(
    current_user_id: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ConversationListResponse:
    """List all conversations for the authenticated user.

    Returns:
        ConversationListResponse: A list of conversation metadata objects
        including id, title, and timestamps, ordered by most recently updated.
    """
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == uuid.UUID(current_user_id))
        .order_by(desc(Conversation.updated_at))
    )
    result = await session.execute(stmt)
    conversations = result.scalars().all()

    return ConversationListResponse(
        conversations=[
            {
                "id": c.id,
                "title": c.title,
                "created_at": c.created_at,
                "updated_at": c.updated_at
            }
            for c in conversations
        ]
    )


@router.get(
    "/chat/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="Get Conversation History",
    description=(
        "Returns the full message history for a specific conversation, "
        "ensuring the user owns it."
    ),
)
async def get_conversation(
    conversation_id: str,
    current_user_id: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ConversationDetailResponse:
    """Retrieve the full history of a single conversation.

    Validates that the conversation belongs to the authenticated user before
    returning it, preventing horizontal privilege escalation.

    Args:
        conversation_id: The UUID of the conversation to retrieve.

    Returns:
        ConversationDetailResponse: The conversation metadata plus the full
        list of messages.

    Raises:
        HTTPException: 400 if the conversation ID is malformed, 404 if the
        conversation does not exist or does not belong to the user.
    """
    try:
        conv_uuid = uuid.UUID(conversation_id)
    except ValueError as err:
        raise HTTPException(status_code=400, detail="Invalid conversation ID") from err

    conv = (await session.execute(
        select(Conversation)
        .where(Conversation.id == conv_uuid)
        .where(Conversation.user_id == uuid.UUID(current_user_id))
    )).scalar_one_or_none()

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationDetailResponse(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=conv.messages
    )


from fastapi.responses import StreamingResponse
from app.agent.agent import run_agent_stream

@router.post(
    "/chat/stream",
    summary="Stream Chat Interaction",
    description="Stream ADK SSE events.",
)
@limiter.limit("20/minute")
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    current_user_id: str = Depends(get_current_user),
) -> StreamingResponse:
    try:
        generator = run_agent_stream(
            user_id=current_user_id,
            message=payload.message,
        )
        return StreamingResponse(generator, media_type="text/event-stream")
    except Exception as err:
        logger.exception("Error in chat_stream: %s", err)
        raise HTTPException(status_code=500, detail="Streaming failed") from err
