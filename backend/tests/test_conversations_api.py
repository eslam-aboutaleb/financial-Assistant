"""
Tests for the conversations API endpoints.

Uses mocked database sessions so tests stay fast and isolated from the
real Postgres instance.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.conversations import list_conversations
from app.models.conversation import Conversation
from app.schemas.models import ConversationDetailResponse, ConversationListResponse


def _make_conversation(user_id: str, **overrides):
    data = {
        "id": uuid.uuid4(),
        "user_id": uuid.UUID(user_id),
        "session_id": f"session-{uuid.uuid4().hex[:8]}",
        "title": "Test conversation",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "messages": [],
        **overrides,
    }
    return data


def _mock_conversation_row(**overrides):
    row = MagicMock()
    row.id = overrides.get("id", uuid.uuid4())
    row.user_id = overrides.get("user_id", uuid.UUID("00000000-0000-0000-0000-000000000001"))
    row.title = overrides.get("title", "Test conversation")
    row.created_at = overrides.get("created_at", datetime.now(timezone.utc))
    row.updated_at = overrides.get("updated_at", datetime.now(timezone.utc))
    row.messages = overrides.get("messages", [])
    row.session_id = overrides.get("session_id", "session-123")
    return row


@pytest.mark.asyncio
async def test_list_conversations_returns_old_and_new():
    """List endpoint should return all conversations, including older ones."""
    user_id = "00000000-0000-0000-0000-000000000001"
    old_conv = _mock_conversation_row(user_id=uuid.UUID(user_id), title="Old conversation", updated_at="2026-01-01T00:00:00+00:00")
    new_conv = _mock_conversation_row(user_id=uuid.UUID(user_id), title="New conversation", updated_at="2026-01-02T00:00:00+00:00")

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [new_conv, old_conv]

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    response = await list_conversations(current_user_id=user_id, session=mock_session)
    assert isinstance(response, ConversationListResponse)
    assert len(response.conversations) == 2
    titles = [c.title for c in response.conversations]
    assert "Old conversation" in titles
    assert "New conversation" in titles


@pytest.mark.asyncio
async def test_list_conversations_ordered_by_updated_at():
    """Conversations should be returned with the most recently updated first."""
    user_id = "00000000-0000-0000-0000-000000000001"
    first = _mock_conversation_row(user_id=uuid.UUID(user_id), title="First", updated_at="2026-01-01T00:00:00+00:00")
    second = _mock_conversation_row(user_id=uuid.UUID(user_id), title="Second", updated_at="2026-01-02T00:00:00+00:00")

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [second, first]

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    response = await list_conversations(current_user_id=user_id, session=mock_session)
    assert len(response.conversations) == 2
    assert response.conversations[0].title == "Second"
    assert response.conversations[1].title == "First"


@pytest.mark.asyncio
async def test_list_conversations_scoped_to_user():
    """List endpoint must only return conversations for the authenticated user."""
    user_id = "00000000-0000-0000-0000-000000000001"
    other_user = "00000000-0000-0000-0000-000000000002"

    my_conv = _mock_conversation_row(user_id=uuid.UUID(user_id), title="My conversation")
    other_conv = _mock_conversation_row(user_id=uuid.UUID(other_user), title="Other conversation")

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [my_conv]

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    response = await list_conversations(current_user_id=user_id, session=mock_session)
    assert len(response.conversations) == 1
    assert response.conversations[0].title == "My conversation"

    # Verify the query filtered by the correct user_id.
    called_stmt = mock_session.execute.call_args[0][0]
    assert "user_id" in str(called_stmt)


@pytest.mark.asyncio
async def test_get_conversation_by_id_returns_history():
    """Retrieving a conversation by ID should return its message history."""
    user_id = "00000000-0000-0000-0000-000000000001"
    conv_id = uuid.uuid4()

    conv = _mock_conversation_row(id=conv_id, user_id=uuid.UUID(user_id), title="History conversation")
    msg1 = MagicMock()
    msg1.id = uuid.uuid4()
    msg1.role = "user"
    msg1.content = "Hello"
    msg1.timestamp = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    msg1.message_metadata = {}

    msg2 = MagicMock()
    msg2.id = uuid.uuid4()
    msg2.role = "assistant"
    msg2.content = "Hi there"
    msg2.timestamp = datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc)
    msg2.message_metadata = {"sources": [], "tool_calls": []}

    mock_conv_result = MagicMock()
    mock_conv_result.scalar_one_or_none.return_value = conv

    mock_msg_result = MagicMock()
    mock_msg_result.scalars.return_value.all.return_value = [msg1, msg2]

    mock_session = AsyncMock()
    mock_session.execute.side_effect = [mock_conv_result, mock_msg_result]

    from app.api.v1.conversations import get_conversation

    response = await get_conversation(conversation_id=str(conv_id), current_user_id=user_id, session=mock_session)
    assert isinstance(response, ConversationDetailResponse)
    assert response.id == conv_id
    assert response.title == "History conversation"
    assert len(response.messages) == 2
    assert response.messages[0]["role"] == "user"
    assert response.messages[0]["content"] == "Hello"
    assert response.messages[1]["role"] == "assistant"
    assert response.messages[1]["content"] == "Hi there"


@pytest.mark.asyncio
async def test_get_conversation_not_found_returns_404():
    """A valid conversation ID that does not belong to the user should return 404."""
    from fastapi import HTTPException

    user_id = "00000000-0000-0000-0000-000000000001"
    conv_id = uuid.uuid4()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    from app.api.v1.conversations import get_conversation

    with pytest.raises(HTTPException) as exc_info:
        await get_conversation(conversation_id=str(conv_id), current_user_id=user_id, session=mock_session)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_sidebar_ids_match_list_response():
    """Conversation IDs returned by list should match those used by the sidebar."""
    user_id = "00000000-0000-0000-0000-000000000001"
    conv_a = _mock_conversation_row(user_id=uuid.UUID(user_id), title="Conversation A", session_id="a")
    conv_b = _mock_conversation_row(user_id=uuid.UUID(user_id), title="Conversation B", session_id="b")

    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = [conv_a, conv_b]

    detail_result = MagicMock()
    detail_result.scalar_one_or_none.return_value = conv_a

    msg_result = MagicMock()
    msg_result.scalars.return_value.all.return_value = []

    mock_session = AsyncMock()
    mock_session.execute.side_effect = [list_result, detail_result, msg_result]

    list_response = await list_conversations(current_user_id=user_id, session=mock_session)
    assert len(list_response.conversations) == 2
    returned_ids = [str(c.id) for c in list_response.conversations]
    assert str(conv_a.id) in returned_ids
    assert str(conv_b.id) in returned_ids


@pytest.mark.asyncio
async def test_old_conversations_remain_visible_across_sessions():
    """Conversations created earlier should still appear in later list calls."""
    user_id = "00000000-0000-0000-0000-000000000001"

    old_conv = _mock_conversation_row(
        user_id=uuid.UUID(user_id),
        title="Old conversation",
        updated_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    new_conv = _mock_conversation_row(
        user_id=uuid.UUID(user_id),
        title="New conversation",
        updated_at=datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
    )

    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = [new_conv, old_conv]

    mock_session = AsyncMock()
    mock_session.execute.return_value = list_result

    # First session: list conversations
    first_response = await list_conversations(current_user_id=user_id, session=mock_session)
    assert len(first_response.conversations) == 2
    old_ids = [c.id for c in first_response.conversations]
    assert str(old_conv.id) in [str(i) for i in old_ids]

    # Second session: list again with a fresh mock result
    list_result2 = MagicMock()
    list_result2.scalars.return_value.all.return_value = [new_conv, old_conv]
    mock_session2 = AsyncMock()
    mock_session2.execute.return_value = list_result2

    second_response = await list_conversations(current_user_id=user_id, session=mock_session2)
    assert len(second_response.conversations) == 2
    second_ids = [c.id for c in second_response.conversations]
    assert str(old_conv.id) in [str(i) for i in second_ids]
    assert str(new_conv.id) in [str(i) for i in second_ids]


@pytest.mark.asyncio
async def test_sidebar_click_id_returns_correct_conversation():
    """IDs shown in the sidebar should resolve to the correct conversation detail."""
    user_id = "00000000-0000-0000-0000-000000000001"
    conv_id = uuid.uuid4()

    conv = _mock_conversation_row(id=conv_id, user_id=uuid.UUID(user_id), title="Sidebar click")

    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = [conv]

    detail_result = MagicMock()
    detail_result.scalar_one_or_none.return_value = conv

    msg_result = MagicMock()
    msg_result.scalars.return_value.all.return_value = []

    mock_session = AsyncMock()
    mock_session.execute.side_effect = [list_result, detail_result, msg_result]

    # List conversations (sidebar)
    list_response = await list_conversations(current_user_id=user_id, session=mock_session)
    assert len(list_response.conversations) == 1
    sidebar_conv = list_response.conversations[0]
    assert sidebar_conv.title == "Sidebar click"

    # Click the conversation ID from the sidebar
    from app.api.v1.conversations import get_conversation

    detail_response = await get_conversation(
        conversation_id=str(sidebar_conv.id),
        current_user_id=user_id,
        session=mock_session,
    )
    assert detail_response.id == sidebar_conv.id
    assert detail_response.title == "Sidebar click"


@pytest.mark.asyncio
async def test_new_chat_does_not_break_existing_sidebar_conversations():
    """Creating a new chat should not remove or corrupt existing conversations."""
    user_id = "00000000-0000-0000-0000-000000000001"

    existing = _mock_conversation_row(
        user_id=uuid.UUID(user_id),
        title="Existing conversation",
        updated_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )
    new_chat = _mock_conversation_row(
        user_id=uuid.UUID(user_id),
        title="New chat",
        updated_at=datetime(2026, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
    )

    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = [new_chat, existing]

    mock_session = AsyncMock()
    mock_session.execute.return_value = list_result

    response = await list_conversations(current_user_id=user_id, session=mock_session)
    assert len(response.conversations) == 2
    titles = [c.title for c in response.conversations]
    assert "Existing conversation" in titles
    assert "New chat" in titles
