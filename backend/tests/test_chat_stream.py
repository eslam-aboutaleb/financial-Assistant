import pytest
import uuid
from unittest.mock import patch


@pytest.mark.asyncio
async def test_chat_stream_empty_message(test_client, mock_current_user):
    response = test_client.post(
        "/api/v1/chat/stream", json={"message": ""}, headers=mock_current_user
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_chat_stream_invalid_json(test_client, mock_current_user):
    response = test_client.post("/api/v1/chat/stream", data="invalid", headers=mock_current_user)
    assert response.status_code == 422


@pytest.mark.asyncio
@patch("app.api.v1.chat_stream.run_agent_stream")
async def test_chat_stream_valid(mock_run_agent_stream, test_client, mock_current_user):
    async def mock_run(*args, **kwargs):
        yield b'data: {"type": "content", "content": "Hello"}\n\n'

    mock_run_agent_stream.return_value = mock_run()

    response = test_client.post(
        "/api/v1/auth/signup",
        json={"username": f"stream_user_{uuid.uuid4().hex[:8]}", "password": "TestPass123!"},
    )
    token = response.json()["access_token"]

    response2 = test_client.post(
        "/api/v1/chat/stream", json={"message": "Hi"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert response2.status_code == 200
