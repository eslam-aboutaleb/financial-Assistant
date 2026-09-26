"""
Pytest configuration and shared fixtures for the OmniCare Financial backend test suite.

Provides fixtures for:
 - test_client: FastAPI TestClient instance configured for testing
 - sample_claims_path: Isolated temporary copy of mock_claims.json
 - mock_current_user: Overrides the get_current_user dependency with a fixed test user ID
"""

import asyncio
import json
import os
import shutil
import sys
import warnings
from pathlib import Path

import pytest
from unittest.mock import patch


def _in_docker() -> bool:
    try:
        return Path("/.dockerenv").exists() or (
            Path("/proc/self/cgroup").exists()
            and "docker" in Path("/proc/self/cgroup").read_text(errors="ignore")
        )
    except Exception:
        return False


DB_HOST = "db" if _in_docker() else "localhost"
os.environ["DATABASE_URL"] = (
    f"postgresql+asyncpg://omnicare:omnicare_password@{DB_HOST}:5432/omnicare"
)

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings  # noqa: E402


# Patch ingest_policy to avoid network calls during test client startup.
# Import and keep the real function before patching so e2e tests can use it.
import app.main as _app_main_module  # noqa: E402, PLC0415

_real_ingest_policy = _app_main_module.ingest_policy
_ingest_policy_patcher = patch(
    "app.main.ingest_policy", new_callable=__import__("unittest.mock").mock.AsyncMock
)
_ingest_policy_patcher.start()


@pytest.fixture(scope="function")
def real_ingest_policy():
    """Stop the global ingest_policy mock and restore the real function for e2e tests."""
    _ingest_policy_patcher.stop()
    yield _real_ingest_policy
    _ingest_policy_patcher.start()


@pytest.fixture(scope="function")
def sample_claims_path(tmp_path, monkeypatch):
    """
    Fixture providing an isolated temporary copy of mock_claims.json.

    Copies the baseline mock_claims.json into a temporary directory and
    patches settings.claims_file_path so tool invocations do not affect
    the repository's baseline data or bleed across tests.
    """
    original_claims = BACKEND_DIR / "app" / "data" / "mock_claims.json"
    temp_claims = tmp_path / "mock_claims.json"

    if original_claims.exists():
        shutil.copy(original_claims, temp_claims)
    else:
        baseline = [
            {
                "claim_id": "CLM-8821",
                "policy_number": "POL-1092",
                "claim_type": "Water Damage",
                "status": "Approved",
                "amount": 3500.00,
                "description": "Pipe burst causing kitchen flooding and water damage.",
            },
            {
                "claim_id": "CLM-9014",
                "policy_number": "POL-3341",
                "claim_type": "Personal Property",
                "status": "Under Review",
                "amount": 1200.00,
                "description": "Burglary resulting in stolen electronics and furniture.",
            },
        ]
        temp_claims.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

    if hasattr(settings, "claims_file_path"):
        monkeypatch.setattr(settings, "claims_file_path", str(temp_claims))

    return temp_claims


@pytest.fixture(scope="function")
def test_client(sample_claims_path):
    """
    FastAPI TestClient fixture configured with isolated claims data.
    """
    from fastapi.testclient import TestClient  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415
    from app.database import engine  # noqa: PLC0415

    with TestClient(app) as client:
        yield client

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                asyncio.run(engine.dispose())
            else:
                pending = [
                    task
                    for task in asyncio.all_tasks(loop=loop)
                    if not task.done() and task != asyncio.current_task()
                ]
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.run_until_complete(engine.dispose())
    except Exception as exc:  # pragma: no cover - surfaced in test output
        print(f"[test_client] engine dispose failed: {exc!r}")
        raise

    import time

    time.sleep(0.1)


@pytest.fixture(scope="function", autouse=True)
def _reset_engine():
    yield
    try:
        from app.database import engine  # noqa: PLC0415

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                asyncio.run(engine.dispose())
            else:
                pending = [
                    task
                    for task in asyncio.all_tasks(loop=loop)
                    if not task.done() and task != asyncio.current_task()
                ]
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.run_until_complete(engine.dispose())
    except Exception as exc:  # pragma: no cover - cleanup best-effort
        print(f"[_reset_engine] post-test cleanup failed: {exc!r}")


_TEST_USER_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture(autouse=False)
def mock_current_user():
    """
    Override the get_current_user dependency so chat/idempotency tests can run
    without hitting the real auth/database stack.

    Returns a dict mimicking Authorization headers (the override itself bypasses
    header validation, but the fixture is available for tests that want to pass
    explicit headers).
    """
    from app.auth import get_current_user  # noqa: PLC0415
    from app.main import app  # noqa: PLC0415

    async def _override_get_current_user():
        return _TEST_USER_ID

    app.dependency_overrides[get_current_user] = _override_get_current_user
    yield {"Authorization": f"Bearer test-token-for-{_TEST_USER_ID}"}
    app.dependency_overrides.pop(get_current_user, None)


class MockEmbeddingResponse:
    def __init__(self, num_inputs):
        self.data = [{"embedding": [0.0] * 1536} for _ in range(num_inputs)]


def mock_litellm_embedding(**kwargs):
    inputs = kwargs.get("input", [])
    num_inputs = len(inputs) if isinstance(inputs, list) else 1
    return MockEmbeddingResponse(num_inputs)


_litellm_patcher = patch("litellm.embedding", side_effect=mock_litellm_embedding)
_litellm_patcher.start()
