"""
Tests for versioned policy ingestion (Feature 15: document-version-model).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.policy import Policy
from app.models.policy_version import PolicyVersion
from app.rag.ingest import ingest_policy


# --- Version model tests ---


def test_policy_version_effective_from_and_source_hash_non_null():
    """PolicyVersion requires effective_from and source_hash non-null at the ORM level."""
    from app.models.policy_version import PolicyVersion as PV

    assert "effective_from" in PV.__table__.c
    assert "source_hash" in PV.__table__.c
    assert PV.__table__.c["effective_from"].nullable is False
    assert PV.__table__.c["source_hash"].nullable is False


@pytest.mark.asyncio
async def test_ingest_policy_creates_policy_and_version_when_missing(tmp_path):
    """ingest_policy() creates Policy and PolicyVersion when none exist."""
    md_file = tmp_path / "policy.md"
    md_file.write_text("# Policy\n\nTest content.", encoding="utf-8")
    file_content = md_file.read_text(encoding="utf-8")

    chunks = [
        {
            "id": "chunk_1",
            "text": "test policy text",
            "metadata": {"section": "Test", "source": "policy.md", "chunk_index": 0, "sub_chunk_index": 0},
        }
    ]
    mock_store = AsyncMock()
    mock_store.count.return_value = 0

    with (
        patch("app.rag.ingest.get_vector_store", return_value=mock_store),
        patch("app.rag.ingest.chunk_policy_document", return_value=chunks),
        patch("app.rag.ingest.EmbeddingFactory.get_embedding_function") as mock_embed,
        patch("app.rag.ingest.async_session_factory") as mock_session_factory,
        patch("app.rag.ingest.hashlib.sha256") as mock_sha,
        patch("builtins.open", MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value=file_content)))))),
    ):
        mock_sha.return_value.hexdigest.return_value = "newhash123"
        mock_embed.return_value = AsyncMock(return_value=[[0.1] * 1536 for _ in chunks])

        mock_session = AsyncMock()
        mock_policy_result = MagicMock()
        mock_policy_result.scalar_one_or_none.return_value = None
        mock_version_result = MagicMock()
        mock_version_result.scalar_one_or_none.return_value = None

        def make_execute_result(*args, **kwargs):
            result = MagicMock()
            query_str = str(args[0]) if args else ""
            if "SELECT" in query_str and "policies" in query_str:
                result.scalar_one_or_none.return_value = None
            elif "SELECT" in query_str and "policy_versions" in query_str:
                result.scalar_one_or_none.return_value = None
            elif "pg_advisory" in query_str:
                result.scalar_one.return_value = 0
            elif "DELETE" in query_str:
                result.rowcount = 0
            else:
                result.mappings.return_value.first.return_value = None
            return result

        mock_session.execute.side_effect = make_execute_result
        mock_session.flush = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        count = await ingest_policy(policy_path=str(md_file))
        assert count == len(chunks)
        mock_store.upsert.assert_called_once()
        # upsert is called with positional arg: await store.upsert(chunks, session=session)
        upserted_chunks = mock_store.upsert.call_args[0][0]
        assert all("policy_id" in c for c in upserted_chunks)
        assert all("policy_version_id" in c for c in upserted_chunks)


@pytest.mark.asyncio
async def test_ingest_policy_skips_when_hash_unchanged(tmp_path):
    """ingest_policy() skips ingestion when the active version's hash matches."""
    md_file = tmp_path / "policy.md"
    md_file.write_text("# Policy\n\nTest content.", encoding="utf-8")
    file_content = md_file.read_text(encoding="utf-8")

    mock_store = AsyncMock()
    mock_store.count.return_value = 5

    with (
        patch("app.rag.ingest.get_vector_store", return_value=mock_store),
        patch("app.rag.ingest.async_session_factory") as mock_session_factory,
        patch("app.rag.ingest.hashlib.sha256") as mock_sha,
        patch("builtins.open", MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value=file_content)))))),
    ):
        mock_sha.return_value.hexdigest.return_value = "storedhash"
        mock_session = AsyncMock()
        existing_policy = Policy(
            policy_id="00000000-0000-0000-0000-000000000001",
            product="omnicare_base",
            jurisdiction="US",
            is_active=True,
        )
        old_version = PolicyVersion(
            version_id="00000000-0000-0000-0000-000000000002",
            policy_id="00000000-0000-0000-0000-000000000001",
            version="current",
            effective_from=datetime(2026, 9, 1, tzinfo=UTC),
            effective_to=None,
            source_hash="storedhash",
            embedding_model="text-embedding-3-small",
            embedding_dim=1536,
            chunker_version="v1",
            chunk_size=600,
            overlap=100,
            retrieval_schema_version="v1",
        )

        def make_execute_result(*args, **kwargs):
            result = MagicMock()
            query_str = str(args[0]) if args else ""
            if "SELECT" in query_str and "policies" in query_str:
                result.scalar_one_or_none.return_value = existing_policy
            elif "SELECT" in query_str and "policy_versions" in query_str:
                result.scalar_one_or_none.return_value = old_version
            elif "pg_advisory" in query_str:
                result.scalar_one.return_value = 0
            elif "SELECT" in query_str and "COUNT" in query_str:
                result.scalar_one.return_value = 5
            else:
                result.mappings.return_value.first.return_value = None
            return result

        mock_session.execute.side_effect = make_execute_result
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        count = await ingest_policy(policy_path=str(md_file))
        assert count == 5
        mock_store.upsert.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_policy_closes_old_version_and_creates_new(tmp_path):
    """ingest_policy() closes the old version and creates a new one when hash changes."""
    md_file = tmp_path / "policy.md"
    md_file.write_text("# Policy\n\nChanged content.", encoding="utf-8")
    file_content = md_file.read_text(encoding="utf-8")

    chunks = [
        {
            "id": "chunk_1",
            "text": "test policy text",
            "metadata": {"section": "Test", "source": "policy.md", "chunk_index": 0, "sub_chunk_index": 0},
        }
    ]
    mock_store = AsyncMock()
    mock_store.count.return_value = 0

    with (
        patch("app.rag.ingest.get_vector_store", return_value=mock_store),
        patch("app.rag.ingest.chunk_policy_document", return_value=chunks),
        patch("app.rag.ingest.EmbeddingFactory.get_embedding_function") as mock_embed,
        patch("app.rag.ingest.async_session_factory") as mock_session_factory,
        patch("app.rag.ingest.hashlib.sha256") as mock_sha,
        patch("app.rag.ingest.datetime") as mock_dt,
        patch("builtins.open", MagicMock(return_value=MagicMock(__enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value=file_content)))))),
    ):
        fake_now = datetime(2026, 10, 2, 12, 0, 0, tzinfo=UTC)
        mock_dt.now.return_value = fake_now
        mock_sha.return_value.hexdigest.return_value = "newhash456"
        mock_embed.return_value = AsyncMock(return_value=[[0.1] * 1536 for _ in chunks])

        mock_session = AsyncMock()
        existing_policy = Policy(
            policy_id="00000000-0000-0000-0000-000000000001",
            product="omnicare_base",
            jurisdiction="US",
            is_active=True,
        )
        old_version = PolicyVersion(
            version_id="00000000-0000-0000-0000-000000000002",
            policy_id="00000000-0000-0000-0000-000000000001",
            version="current",
            effective_from=datetime(2026, 9, 1, tzinfo=UTC),
            effective_to=None,
            source_hash="oldhash",
        )

        def make_execute_result(*args, **kwargs):
            result = MagicMock()
            query_str = str(args[0]) if args else ""
            if "SELECT" in query_str and "policies" in query_str:
                result.scalar_one_or_none.return_value = existing_policy
            elif "SELECT" in query_str and "policy_versions" in query_str:
                result.scalar_one_or_none.return_value = old_version
            elif "pg_advisory" in query_str:
                result.scalar_one.return_value = 0
            elif "DELETE" in query_str:
                result.rowcount = 0
            else:
                result.mappings.return_value.first.return_value = None
            return result

        mock_session.execute.side_effect = make_execute_result
        mock_session.flush = AsyncMock()
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        count = await ingest_policy(policy_path=str(md_file))
        assert count == len(chunks)
        assert old_version.effective_to == fake_now
        mock_store.upsert.assert_called_once()
        # upsert is called with positional arg: await store.upsert(chunks, session=session)
        upserted_chunks = mock_store.upsert.call_args[0][0]
        assert all("policy_id" in c for c in upserted_chunks)
        assert all("policy_version_id" in c for c in upserted_chunks)
