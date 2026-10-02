"""Coverage tests for app.agent.conversation_store uncovered paths."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestConversationStore:
    @pytest.mark.asyncio
    async def test_save_conversation_turn_creates_new(self):
        from app.agent.conversation_store import save_conversation_turn

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=lambda: None)
        )

        with patch("app.agent.conversation_store.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__.return_value = mock_session
            await save_conversation_turn(
                user_id="00000000-0000-0000-0000-000000000001",
                session_id="session-1",
                message="hello",
                response_text="hi",
                sources=[],
                tool_calls=[],
            )
            mock_session.add.assert_called()
            mock_session.commit.assert_called()
