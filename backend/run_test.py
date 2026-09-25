import asyncio
from httpx import ASGITransport, AsyncClient
from fastapi.testclient import TestClient

def run():
    from app.main import app
    from tests.conftest import _TEST_USER_ID

    client = TestClient(app)
    # mock auth
    headers = {"Authorization": f"Bearer test-token"}
    app.dependency_overrides = {}
    from app.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: _TEST_USER_ID

    # We need to simulate the environment
    payload = {
        "message": "What is covered under water damage from a burst pipe?",
    }
    response = client.post(
        "/api/v1/chat",
        json=payload,
        headers=headers,
    )
    print(response.status_code)
    print(response.json())

if __name__ == "__main__":
    run()
