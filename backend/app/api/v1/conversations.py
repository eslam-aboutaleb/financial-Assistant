"""
Conversation history endpoints.

GET /api/v1/chat/conversations - List the authenticated user's conversations.
GET /api/v1/chat/conversations/{id} - Retrieve a single conversation's history.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import uuid

from app.auth import get_current_user
from app.database import get_db
from app.models.conversation import Conversation
from app.schemas.models import ConversationListResponse, ConversationDetailResponse

logger = logging.getLogger(__name__)

router = APIRouter()


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
                "updated_at": c.updated_at,
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

    conv = (
        await session.execute(
            select(Conversation)
            .where(Conversation.id == conv_uuid)
            .where(Conversation.user_id == uuid.UUID(current_user_id))
        )
    ).scalar_one_or_none()

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationDetailResponse(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=conv.messages,
    )
