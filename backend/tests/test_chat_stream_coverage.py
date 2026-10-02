"""Coverage tests for app.api.v1.chat_stream uncovered paths."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestChatStreamAPI:
    def test_transform_adk_event_invalid_json_fallback(self):
        from app.api.v1.chat_stream import _transform_adk_event

        result = _transform_adk_event("not-valid-json")
        assert result.startswith("data:")

    def test_transform_adk_event_final_response_with_sources(self):
        from app.api.v1.chat_stream import _transform_adk_event

        event = {"is_final_response": True}
        event_json = json.dumps(event)
        sources = [{"section": "Section 1", "source": "policy.md"}]
        result = _transform_adk_event(event_json, sources=sources)
        assert "response_complete" in result
        assert "Section 1" in result

    def test_transform_adk_event_raw_passthrough(self):
        from app.api.v1.chat_stream import _transform_adk_event

        raw = '{"type": "other", "data": "raw"}'
        result = _transform_adk_event(raw)
        assert result == f"data: {raw}\n\n"

    def test_chat_stream_client_disconnect(self, test_client, mock_current_user):
        async def mock_run(*args, **kwargs):
            yield 'data: {"type": "text_delta", "content": "Hello"}\n\n'

        with patch("app.api.v1.chat_stream.run_agent_stream") as mock_run_agent_stream:
            mock_run_agent_stream.return_value = mock_run()
            response = test_client.post(
                "/api/v1/chat/stream",
                json={"message": "Hi"},
                headers=mock_current_user,
            )
            assert response.status_code == 200

    def test_chat_stream_value_error_context_suppressed(self, test_client, mock_current_user):
        async def mock_run(*args, **kwargs):
            yield 'data: {"type": "text_delta", "content": "Hello"}\n\n'
            raise ValueError("was created in a different Context")

        with patch("app.api.v1.chat_stream.run_agent_stream") as mock_run_agent_stream:
            mock_run_agent_stream.return_value = mock_run()
            response = test_client.post(
                "/api/v1/chat/stream",
                json={"message": "Hi"},
                headers=mock_current_user,
            )
            assert response.status_code == 200
            assert "response_complete" in response.text

    def test_chat_stream_value_error_not_context_mismatch(self, test_client, mock_current_user):
        async def mock_run(*args, **kwargs):
            yield 'data: {"type": "text_delta", "content": "Hello"}\n\n'
            raise ValueError("some other ValueError")

        with patch("app.api.v1.chat_stream.run_agent_stream") as mock_run_agent_stream:
            mock_run_agent_stream.return_value = mock_run()
            response = test_client.post(
                "/api/v1/chat/stream",
                json={"message": "Hi"},
                headers=mock_current_user,
            )
            assert response.status_code == 200
            assert "response_complete" in response.text

    def test_chat_stream_generic_exception_yields_error(self, test_client, mock_current_user):
        async def mock_run(*args, **kwargs):
            raise RuntimeError("stream broken")

        with patch("app.api.v1.chat_stream.run_agent_stream") as mock_run_agent_stream:
            mock_run_agent_stream.return_value = mock_run()
            response = test_client.post(
                "/api/v1/chat/stream",
                json={"message": "Hi"},
                headers=mock_current_user,
            )
            assert response.status_code == 200
            assert "response_complete" in response.text

    def test_persist_streamed_turn_logs_error(self):
        from app.api.v1.chat_stream import _persist_streamed_turn

        with patch("app.api.v1.chat_stream.save_conversation_turn", new_callable=AsyncMock) as mock_save:
            mock_save.side_effect = Exception("DB error")
            with patch("app.api.v1.chat_stream.logger") as mock_logger:
                import asyncio
                asyncio.run(
                    _persist_streamed_turn(
                        user_id="00000000-0000-0000-0000-000000000001",
                        session_id="session-1",
                        message="hello",
                        result=MagicMock(final_text_parts=["hello"], sources=[], tool_calls=[]),
                    )
                )
                mock_logger.error.assert_called()
