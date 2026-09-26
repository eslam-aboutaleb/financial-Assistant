"""
Streaming chat endpoint.

POST /api/v1/chat/stream - Stream ADK SSE events for real-time chat responses.

This endpoint returns a ``StreamingResponse`` that emits Server-Sent Events
(SSE) formatted strings produced by the Google ADK agent runner. The client
is responsible for parsing the SSE stream and rendering partial responses
as they arrive.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.agent.agent import run_agent_stream
from app.auth import get_current_user
from app.rate_limiter import limiter
from app.schemas.models import ChatRequest

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/chat/stream",
    summary="Stream Chat Interaction",
    description="Stream ADK SSE events for real-time chat responses.",
    responses={
        status.HTTP_200_OK: {
            "description": "SSE stream of agent response events.",
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Validation error: missing or invalid message format.",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Internal server error during streaming.",
        },
    },
)
@limiter.limit("20/minute")
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    current_user_id: str = Depends(get_current_user),
) -> StreamingResponse:
    """Stream a chat interaction response as Server-Sent Events.

    Validates the request payload, then delegates to the ADK agent runner
    in streaming mode. Each ADK event is serialized to JSON and yielded as
    an SSE ``data:`` chunk.

    Args:
        payload: Validated chat request containing the user message.
        request: The incoming FastAPI request (used for rate limiting).
        current_user_id: The authenticated user's UUID (injected by dependency).

    Returns:
        StreamingResponse: An SSE stream with media type
        ``text/event-stream``.

    Raises:
        HTTPException: 422 if the message is empty or whitespace-only.
        HTTPException: 500 if the streaming generator raises an unexpected error.
    """
    message = payload.message

    if not message.strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty")

    try:
        generator = run_agent_stream(
            user_id=current_user_id,
            message=message,
        )
        return StreamingResponse(generator, media_type="text/event-stream")
    except Exception as err:
        logger.exception("Error in chat_stream: %s", err)
        raise HTTPException(status_code=500, detail="Streaming failed") from err
