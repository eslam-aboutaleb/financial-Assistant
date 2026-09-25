"""
Conversation persistence helpers.

This module owns all database interactions for chat conversations so that
the agent layer stays framework-agnostic and testable.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, UTC

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.database import async_session_factory
from app.models.conversation import Conversation

logger = logging.getLogger(__name__)


async def save_conversation_turn(
    user_id: str,
    session_id: str,
    message: str,
    response_text: str,
    sources: list[str],
    tool_calls: list[dict],
) -> None:
    """
    Append a user/assistant turn to the conversation history.

    Creates a new conversation row if none exists for ``session_id``,
    otherwise extends the existing message list.
    """
    try:
        async with async_session_factory() as db_session:
            conv = (
                await db_session.execute(
                    select(Conversation).where(Conversation.session_id == session_id)
                )
            ).scalar_one_or_none()

            new_msgs = [
                {
                    "id": str(uuid.uuid4()),
                    "role": "user",
                    "content": message,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                {
                    "id": str(uuid.uuid4()),
                    "role": "assistant",
                    "content": response_text,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "sources": sources,
                    "tool_calls": tool_calls,
                },
            ]

            if conv is None:
                title = message[:40] + ("..." if len(message) > 40 else "")
                conv = Conversation(
                    user_id=uuid.UUID(user_id),
                    session_id=session_id,
                    title=title,
                    messages=new_msgs,
                )
                db_session.add(conv)
            else:
                conv.messages.extend(new_msgs)
                flag_modified(conv, "messages")

            await db_session.commit()
    except Exception as exc:  # pragma: no cover - log and continue
        logger.error("Failed to save conversation turn: %s", exc, exc_info=True)
