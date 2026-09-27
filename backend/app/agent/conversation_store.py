"""
Conversation persistence helpers.

This module owns all database interactions for chat conversations so that
the agent layer stays framework-agnostic and testable.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.database import async_session_factory
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage

logger = logging.getLogger(__name__)


async def save_conversation_turn(  # noqa: PLR0913, PLR0917
    user_id: str,
    session_id: str,
    message: str,
    response_text: str,
    sources: list[str],
    tool_calls: list[dict],
) -> None:
    """Append a user/assistant turn to the conversation history.

    Creates a new conversation row if none exists for ``session_id``,
    otherwise extends the existing message list with new rows in the
    normalized ``conversation_messages`` table. The conversation title is
    derived from the first user message for easy identification in the UI.

    This function is intentionally fire-and-forget: it catches and logs
    exceptions without propagating them, so a database failure during
    persistence does not interrupt the chat response stream.

    Args:
        user_id: The authenticated user's UUID string.
        session_id: The ADK session identifier used to group messages into
            a single conversation.
        message: The user's raw chat message.
        response_text: The agent's synthesized response text.
        sources: Citation sources referenced in the response (policy sections,
            claim IDs).
        tool_calls: Trace of tools invoked during agent reasoning, including
            arguments and results.

    Returns:
        None
    """
    try:
        async with async_session_factory() as db_session:
            conv = (
                await db_session.execute(
                    select(Conversation).where(Conversation.session_id == session_id)
                )
            ).scalar_one_or_none()

            if conv is None:
                # Derive a human-readable title from the first message.
                title = message[:40] + ("..." if len(message) > 40 else "")
                conv = Conversation(
                    user_id=uuid.UUID(user_id),
                    session_id=session_id,
                    title=title,
                )
                db_session.add(conv)
                await db_session.flush()

            user_message = ConversationMessage(
                conversation_id=conv.id,
                role="user",
                content=message,
                timestamp=datetime.now(UTC),
                message_metadata=None,
            )
            assistant_message = ConversationMessage(
                conversation_id=conv.id,
                role="assistant",
                content=response_text,
                timestamp=datetime.now(UTC),
                message_metadata=(
                    {"sources": sources, "tool_calls": tool_calls}
                    if sources or tool_calls
                    else None
                ),
            )
            db_session.add(user_message)
            db_session.add(assistant_message)
            await db_session.commit()
    except Exception as exc:  # pragma: no cover - log and continue
        logger.error("Failed to save conversation turn: %s", exc, exc_info=True)
