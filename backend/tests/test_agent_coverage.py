"""Coverage tests for app.agent.agent uncovered paths."""

from __future__ import annotations

import logging
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAgentSessionEviction:
    @pytest.mark.asyncio
    async def test_ensure_session_evicts_oldest_when_at_capacity(self):
        from app.agent.agent import _MAX_SESSIONS, _user_sessions, _ensure_session

        _user_sessions.clear()
        for i in range(_MAX_SESSIONS):
            _user_sessions[f"user-{i}"] = f"session-{i}"

        new_user = f"user-new-{uuid.uuid4().hex[:8]}"
        with patch("app.agent.agent.session_service") as mock_session_service:
            mock_session_service.create_session = AsyncMock()
            mock_session_service.delete_session = AsyncMock()
            session_id = await _ensure_session(new_user)
            assert session_id is not None
            assert len(_user_sessions) == _MAX_SESSIONS
            oldest = next(iter(_user_sessions))
            assert oldest != new_user

    @pytest.mark.asyncio
    async def test_ensure_session_delete_session_exception_logged(self):
        from app.agent.agent import _user_sessions, _ensure_session

        _user_sessions.clear()
        for i in range(500):
            _user_sessions[f"user-{i}"] = f"session-{i}"
        _user_sessions["evict-user"] = "session-evict"
        with patch("app.agent.agent.session_service") as mock_session_service:
            mock_session_service.create_session = AsyncMock()
            mock_session_service.delete_session = AsyncMock(side_effect=Exception("delete failed"))
            with patch("app.agent.agent.logger") as mock_logger:
                await _ensure_session("new-user-after-capacity")
                mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_reset_user_session_delete_exception_logged(self):
        from app.agent.agent import _user_sessions, reset_user_session

        _user_sessions["reset-user"] = "session-reset"
        with patch("app.agent.agent.session_service") as mock_session_service:
            mock_session_service.delete_session = AsyncMock(side_effect=Exception("delete failed"))
            with patch("app.agent.agent.logger") as mock_logger:
                await reset_user_session("reset-user")
                mock_logger.warning.assert_called()
        assert "reset-user" not in _user_sessions


class TestAgentStreamCoverage:
    @pytest.mark.asyncio
    async def test_run_agent_stream_populates_result(self):
        from app.agent.agent import run_agent_stream

        user_id = str(uuid.uuid4())
        mock_event = MagicMock()
        mock_event.is_final_response.return_value = True
        mock_event.content.parts = [MagicMock(text="streamed text")]
        mock_event.model_dump_json.return_value = '{"text": "streamed text"}'

        async def mock_run_async(**kwargs):
            yield mock_event

        mock_runner = MagicMock()
        mock_runner.run_async = mock_run_async

        with patch("app.agent.agent.runner", mock_runner):
            with patch("app.agent.agent.session_service") as mock_session_service:
                mock_session_service.create_session = AsyncMock()
                mock_session_service.delete_session = AsyncMock()
                result = MagicMock()
                chunks = []
                async for chunk in run_agent_stream(user_id=user_id, message="test", result=result):
                    chunks.append(chunk)

        assert result.session_id is not None
        assert result.final_text_parts == ["streamed text"]
        assert result.tool_calls == []
        assert result.sources == []

    @pytest.mark.asyncio
    async def test_run_agent_stream_collects_tool_calls_and_sources(self):
        from app.agent.agent import run_agent_stream

        user_id = str(uuid.uuid4())
        mock_fc = MagicMock()
        mock_fc.name = "query_policy"
        mock_fc.args = {"query": "test"}

        mock_fr = MagicMock()
        mock_fr.name = "query_policy"
        mock_fr.response = {
            "sources": [{"section": "Section 1", "source": "policy.md"}],
            "citation": "Claim CLM-123 in system",
        }

        mock_event_fc = MagicMock()
        mock_event_fc.get_function_calls.return_value = [mock_fc]
        mock_event_fc.get_function_responses.return_value = None
        mock_event_fc.is_final_response.return_value = False
        mock_event_fc.content = None
        mock_event_fc.model_dump_json.return_value = '{"fc": true}'

        mock_event_fr = MagicMock()
        mock_event_fr.get_function_calls.return_value = None
        mock_event_fr.get_function_responses.return_value = [mock_fr]
        mock_event_fr.is_final_response.return_value = True
        mock_event_fr.content.parts = [MagicMock(text="done")]
        mock_event_fr.model_dump_json.return_value = '{"fr": true}'

        async def mock_run_async(**kwargs):
            yield mock_event_fc
            yield mock_event_fr

        mock_runner = MagicMock()
        mock_runner.run_async = mock_run_async

        with patch("app.agent.agent.runner", mock_runner):
            with patch("app.agent.agent.session_service") as mock_session_service:
                mock_session_service.create_session = AsyncMock()
                mock_session_service.delete_session = AsyncMock()
                result = MagicMock()
                async for _ in run_agent_stream(user_id=user_id, message="test", result=result):
                    pass

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "query_policy"
        assert len(result.sources) == 2
        assert result.tool_calls[0].get("result") == mock_fr.response

    @pytest.mark.asyncio
    async def test_run_agent_stream_sources_string_branch(self):
        from app.agent.agent import run_agent_stream

        user_id = str(uuid.uuid4())
        mock_fr = MagicMock()
        mock_fr.name = "query_policy"
        mock_fr.response = {
            "sources": ["plain-string-source"],
        }

        mock_event_fr = MagicMock()
        mock_event_fr.get_function_calls.return_value = None
        mock_event_fr.get_function_responses.return_value = [mock_fr]
        mock_event_fr.is_final_response.return_value = True
        mock_event_fr.content.parts = [MagicMock(text="done")]
        mock_event_fr.model_dump_json.return_value = '{"fr": true}'

        async def mock_run_async(**kwargs):
            yield mock_event_fr

        mock_runner = MagicMock()
        mock_runner.run_async = mock_run_async

        with patch("app.agent.agent.runner", mock_runner):
            with patch("app.agent.agent.session_service") as mock_session_service:
                mock_session_service.create_session = AsyncMock()
                mock_session_service.delete_session = AsyncMock()
                result = MagicMock()
                async for _ in run_agent_stream(user_id=user_id, message="test", result=result):
                    pass

        assert result.sources == ["plain-string-source"]


class TestAgentResetSession:
    @pytest.mark.asyncio
    async def test_reset_user_session_delete_success_logs_debug(self):
        from app.agent.agent import reset_user_session

        mock_session_service = MagicMock()
        mock_session_service.delete_session = AsyncMock(return_value=None)

        with (
            patch("app.agent.agent.session_service", mock_session_service),
            patch("app.agent.agent._user_sessions", {"user-1": "session-1"}),
        ):
            with patch.object(logging.getLogger("app.agent.agent"), "debug") as mock_debug:
                await reset_user_session("user-1")
                mock_session_service.delete_session.assert_awaited_once()
                mock_debug.assert_called_once()
                assert "user-1" in str(mock_debug.call_args)
