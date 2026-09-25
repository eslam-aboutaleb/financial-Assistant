import pytest
from httpx import AsyncClient
from app.main import app
import uuid
from unittest.mock import patch

@pytest.mark.asyncio
async def test_chat_stream_empty_message(test_client):
    response = test_client.post("/api/v1/chat/stream", json={"message": ""})
    assert response.status_code == 400

@pytest.mark.asyncio
async def test_chat_stream_invalid_json(test_client):
    response = test_client.post("/api/v1/chat/stream", data="invalid")
    assert response.status_code == 400

@pytest.mark.asyncio
@patch("app.api.v1.chat_stream.run_agent")
async def test_chat_stream_valid(mock_run_agent, test_client):
    async def mock_run(*args, **kwargs):
        yield {"type": "content", "content": "Hello"}
    mock_run_agent.return_value = mock_run()
    
    # Just need to authenticate
    response = test_client.post("/api/v1/auth/signup", json={"username": f"stream_user_{uuid.uuid4().hex[:8]}", "password": "TestPass123!"})
    token = response.json()["access_token"]
    
    response2 = test_client.post("/api/v1/chat/stream", json={"message": "Hi"}, headers={"Authorization": f"Bearer {token}"})
    assert response2.status_code == 200
