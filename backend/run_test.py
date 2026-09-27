from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.main import app
from tests.conftest import _TEST_USER_ID


def run():
    client = TestClient(app)
    app.dependency_overrides = {}
    app.dependency_overrides[get_current_user] = lambda: _TEST_USER_ID

    headers = {"Authorization": "Bearer test-token"}

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
