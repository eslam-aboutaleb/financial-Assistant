"""
Streaming chat endpoint.

POST /api/v1/chat/stream - Stream ADK SSE events for real-time chat responses.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
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
    description="Stream ADK SSE events.",
)
@limiter.limit("20/minute")
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    current_user_id: str = Depends(get_current_user),
) -> StreamingResponse:
    """Stream a chat interaction response.

    The request body is read directly from the raw request stream and passed
    to the ADK agent runner. Responses are streamed back as Server-Sent Events.
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
