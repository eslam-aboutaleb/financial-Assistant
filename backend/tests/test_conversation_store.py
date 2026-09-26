"""
Tests for app.agent.conversation_store module.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.conversation_store import save_conversation_turn


@pytest.mark.asyncio
async def test_save_conversation_turn_creates_new():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    with patch("app.agent.conversation_store.async_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__.return_value = mock_session

        await save_conversation_turn(
            user_id=str(uuid.uuid4()),
            session_id="test-session",
            message="Hello",
            response_text="Hi there",
            sources=[],
            tool_calls=[],
        )

        assert mock_session.add.called
        assert mock_session.commit.called


@pytest.mark.asyncio
async def test_save_conversation_turn_extends_existing():
    mock_conv = MagicMock()
    mock_conv.messages = []

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_conv

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    with patch("app.agent.conversation_store.async_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__.return_value = mock_session

        await save_conversation_turn(
            user_id=str(uuid.uuid4()),
            session_id="test-session",
            message="Hello",
            response_text="Hi there",
            sources=["source1"],
            tool_calls=[{"name": "test"}],
        )

        assert len(mock_conv.messages) == 2
        assert mock_session.commit.called
