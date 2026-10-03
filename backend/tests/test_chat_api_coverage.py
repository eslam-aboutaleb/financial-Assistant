"""Coverage tests for app.api.v1.chat uncovered paths."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import litellm


class TestChatAPI:
    def test_chat_bad_request_error_tool_call_id_retry(self, test_client, mock_current_user):
        with patch("app.api.v1.chat.run_agent", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                litellm.BadRequestError(
                    message="tool_call_id mismatch",
                    model="gpt-4o-mini",
                    llm_provider="openai",
                ),
                {"response": "retry ok", "sources": [], "tool_calls": [], "session_id": "s1"},
            ]
            with patch("app.api.v1.chat.reset_user_session", new_callable=AsyncMock):
                response = test_client.post(
                    "/api/v1/chat",
                    json={"message": "retry me"},
                    headers=mock_current_user,
                )
                assert response.status_code == 200

    def test_chat_http_exception_re_raised(self, test_client, mock_current_user):
        from fastapi import HTTPException

        with patch("app.api.v1.chat.run_agent", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = HTTPException(status_code=400, detail="bad")
            response = test_client.post(
                "/api/v1/chat",
                json={"message": "hello"},
                headers=mock_current_user,
            )
            assert response.status_code == 400

    def test_chat_reset_endpoint(self, test_client, mock_current_user):
        with patch("app.api.v1.chat.reset_user_session", new_callable=AsyncMock):
            response = test_client.post("/api/v1/chat/reset", headers=mock_current_user)
            assert response.status_code == 204

    def test_chat_exception_logs_and_returns_500(self, test_client, mock_current_user):
        with patch("app.api.v1.chat.run_agent", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = Exception("unexpected")
            with patch("app.api.v1.chat.logger") as mock_logger:
                response = test_client.post(
                    "/api/v1/chat",
                    json={"message": "hello"},
                    headers=mock_current_user,
                )
                assert response.status_code == 500
                mock_logger.exception.assert_called()
