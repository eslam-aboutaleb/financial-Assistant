"""
Pytest configuration and shared fixtures for the OmniCare Financial backend test suite.

Provides fixtures for:
- test_client: FastAPI TestClient instance configured for testing
- sample_claims_path: Isolated temporary copy of mock_claims.json
- mock_chroma_collection: Ephemeral in-memory Chroma collection pre-loaded with policy chunks
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

# Provide a lightweight stub if chromadb is not yet installed in current environment,
# allowing FastAPI app, health endpoint, and chat endpoint tests to run.
try:
    import importlib.util as _il

    _chromadb_available = _il.find_spec("chromadb") is not None
    if _chromadb_available:
        import chromadb  # noqa: F401
except ImportError:
    import types

    class FakeCollection:
        """In-memory collection mirroring Chroma Collection API."""

        def __init__(self, name, embedding_function=None):
            self.name = name
            self.embedding_function = embedding_function
            self.ids = []
            self.documents = []
            self.metadatas = []

        def count(self) -> int:
            return len(self.documents)

        def add(self, ids, documents, metadatas=None):
            for i, doc_id in enumerate(ids):
                if doc_id in self.ids:
                    idx = self.ids.index(doc_id)
                    self.documents[idx] = documents[i]
                    if metadatas:
                        self.metadatas[idx] = metadatas[i]
                else:
                    self.ids.append(doc_id)
                    self.documents.append(documents[i])
                    self.metadatas.append(metadatas[i] if metadatas else {})

        def query(self, query_texts, n_results=3):
            if not self.documents:
                return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

            scores = []
            for doc in self.documents:
                doc_lower = doc.lower()
                query_tokens = [q.lower().strip() for q in query_texts[0].split() if q.strip()]
                score = sum(1 for token in query_tokens if token in doc_lower)
                scores.append(score)

            sorted_indices = sorted(
                range(len(self.documents)),
                key=lambda idx: scores[idx],
                reverse=True,
            )
            chosen = sorted_indices[:n_results]

            docs = [self.documents[i] for i in chosen]
            metas = [self.metadatas[i] for i in chosen]
            distances = [round(0.05 * i, 3) for i in range(len(chosen))]
            return {
                "documents": [docs],
                "metadatas": [metas],
                "distances": [distances],
            }

    class FakeClient:
        """In-memory client mirroring Chroma PersistentClient / Client API."""

        _storage = {}

        def __init__(self, path=None):
            self.path = str(path) if path else "in_memory"
            if self.path not in FakeClient._storage:
                FakeClient._storage[self.path] = {}

        def get_or_create_collection(self, name, embedding_function=None):
            store = FakeClient._storage[self.path]
            if name not in store:
                store[name] = FakeCollection(name, embedding_function)
            return store[name]

        def create_collection(self, name, embedding_function=None):
            store = FakeClient._storage[self.path]
            store[name] = FakeCollection(name, embedding_function)
            return store[name]

        def get_collection(self, name):
            store = FakeClient._storage[self.path]
            if name not in store:
                raise ValueError(f"Collection {name} does not exist.")
            return store[name]

        def list_collections(self):
            store = FakeClient._storage[self.path]
            return list(store.values())

    fake_chromadb = types.ModuleType("chromadb")
    fake_chromadb.Client = FakeClient
    fake_chromadb.PersistentClient = FakeClient

    fake_utils = types.ModuleType("chromadb.utils")
    fake_embed = types.ModuleType("chromadb.utils.embedding_functions")

    class FakeEmbeddingFunction:
        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, input):
            return [[0.0] * 384 for _ in input]

        def embed_query(self, input):
            return self.__call__(input) if isinstance(input, list) else self.__call__([input])[0]

        def embed_documents(self, input):
            return self.__call__(input)

        def name(self):
            return "default"

        is_legacy = False

    fake_embed.SentenceTransformerEmbeddingFunction = FakeEmbeddingFunction
    fake_embed.OpenAIEmbeddingFunction = FakeEmbeddingFunction

    fake_utils.embedding_functions = fake_embed

    sys.modules["chromadb"] = fake_chromadb
    sys.modules["chromadb.utils"] = fake_utils
    sys.modules["chromadb.utils.embedding_functions"] = fake_embed


# Patch ingest_policy to avoid network calls during test client startup
patch("app.main.ingest_policy").start()


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
                loop.run_until_complete(engine.dispose())
    except Exception as exc:  # pragma: no cover - surfaced in test output
        print(f"[test_client] engine dispose failed: {exc!r}")
        raise


@pytest.fixture(scope="function")
def mock_chroma_collection(tmp_path):
    """
    Temporary Chroma in-memory/ephemeral collection pre-loaded with policy documents.
    Uses chromadb.Client() with default embedding or sentence-transformers.
    """
    import chromadb  # noqa: PLC0415
    from chromadb.utils import embedding_functions  # noqa: PLC0415

    client = chromadb.Client()

    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    collection = client.create_collection(
        name="test_ephemeral_policies",
        embedding_function=embed_fn,
    )

    documents = [
        "## Section 1: Home Water Damage Coverage\n\nWater damage caused by sudden pipe bursts is covered up to $25,000 with a $500 deductible. Gradual leaks or flood damage are strictly excluded.",
        "## Section 2: Personal Property Protection\n\nElectronics, furniture, and jewelry are covered up to $10,000 total. Single items exceeding $2,500 require individual appraisal receipts.",
    ]
    ids = ["policy_chunk_0", "policy_chunk_1"]
    metadatas = [
        {
            "section": "Section 1: Home Water Damage Coverage",
            "source": "sample_policy.md",
            "chunk_index": 0,
        },
        {
            "section": "Section 2: Personal Property Protection",
            "source": "sample_policy.md",
            "chunk_index": 1,
        },
    ]

    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )

    return collection


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


# Patch chromadb OpenAIEmbeddingFunction to avoid real API calls in unit tests
import chromadb.utils.embedding_functions as _ef  # noqa: PLC0415


class FakeEmbeddingFunction:
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, input):
        return [[0.0] * 384 for _ in input]

    def embed_query(self, input):
        return self.__call__(input) if isinstance(input, list) else self.__call__([input])[0]

    def embed_documents(self, input):
        return self.__call__(input)

    def name(self):
        return "default"

    is_legacy = False


_ef.OpenAIEmbeddingFunction = FakeEmbeddingFunction
