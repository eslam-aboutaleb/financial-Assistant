"""
Tests for app.rag.ingest module.

Focuses on the advisory lock behavior that prevents the policy ingestion
race condition when multiple backend instances start concurrently.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rag.ingest import _do_ingest, ingest_policy


def _make_session():
    """Create a mock SQLAlchemy async session."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.execute.return_value = MagicMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.mark.asyncio
async def test_do_ingest_skips_when_snapshot_matches():
    """_do_ingest should skip ingestion when the active version snapshot matches."""
    policy_path = "/tmp/policy.md"
    source_hash = "abc123"

    session = _make_session()

    policy = MagicMock()
    policy.policy_id = "policy-1"

    active_version = MagicMock()
    active_version.source_hash = source_hash
    active_version.embedding_model = "text-embedding-3-small"
    active_version.embedding_dim = 1536
    active_version.chunker_version = "v1"
    active_version.chunk_size = 600
    active_version.overlap = 100
    active_version.retrieval_schema_version = "v1"

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = policy
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = active_version

    session.execute.side_effect = [result1, result2]

    with patch("app.rag.ingest.get_vector_store") as mock_store:
        mock_store.return_value.count = AsyncMock(return_value=42)

        result = await _do_ingest(session, policy_path, source_hash)

    assert result == 42


@pytest.mark.asyncio
async def test_do_ingest_performs_ingestion_when_hash_differs():
    """_do_ingest should perform ingestion when the active version hash differs."""
    policy_path = "/tmp/policy.md"
    source_hash = "new_hash"

    session = _make_session()

    policy = MagicMock()
    policy.policy_id = "policy-1"

    active_version = None

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = policy
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = active_version
    result3 = MagicMock()

    session.execute.side_effect = [result1, result2, result3]

    with (
        patch("app.rag.ingest.chunk_policy_document") as mock_chunk,
        patch("app.rag.ingest.EmbeddingFactory") as mock_factory,
        patch("app.rag.ingest.get_vector_store") as mock_store,
        patch("app.rag.ingest._validate_embedding"),
        patch("app.rag.ingest.datetime") as mock_dt,
    ):
        mock_chunk.return_value = [
            {"text": "chunk 1", "metadata": {}},
            {"text": "chunk 2", "metadata": {}},
        ]
        mock_embed_fn = AsyncMock(return_value=[[0.0] * 1536, [0.0] * 1536])
        mock_factory.get_embedding_function.return_value = mock_embed_fn
        mock_store.return_value.upsert = AsyncMock()
        mock_dt.now.return_value = MagicMock()

        result = await _do_ingest(session, policy_path, source_hash)

    assert result == 2
    assert session.add.call_count >= 1


@pytest.mark.asyncio
async def test_ingest_policy_acquires_advisory_lock():
    """ingest_policy should acquire and release an advisory lock."""
    policy_path = "/tmp/policy.md"
    source_hash = "hash"

    with (
        patch("app.rag.ingest.async_session_factory") as mock_factory,
        patch("app.rag.ingest._do_ingest", new_callable=AsyncMock, return_value=5),
        patch("builtins.open", MagicMock()),
        patch("app.rag.ingest.hashlib") as mock_hashlib,
    ):
        mock_hashlib.sha256.return_value.hexdigest.return_value = source_hash
        mock_session = _make_session()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await ingest_policy(policy_path=policy_path)

    assert result == 5
    execute_calls = [str(call[0][0]) for call in mock_session.execute.call_args_list]
    assert any("pg_advisory_lock" in s for s in execute_calls)
    assert any("pg_advisory_unlock" in s for s in execute_calls)


@pytest.mark.asyncio
async def test_ingest_policy_releases_lock_on_failure():
    """ingest_policy should release the advisory lock even if _do_ingest raises."""
    policy_path = "/tmp/policy.md"
    source_hash = "hash"

    with (
        patch("app.rag.ingest.async_session_factory") as mock_factory,
        patch(
            "app.rag.ingest._do_ingest", new_callable=AsyncMock, side_effect=RuntimeError("boom")
        ),
        patch("builtins.open", MagicMock()),
        patch("app.rag.ingest.hashlib") as mock_hashlib,
    ):
        mock_hashlib.sha256.return_value.hexdigest.return_value = source_hash
        mock_session = _make_session()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(RuntimeError, match="boom"):
            await ingest_policy(policy_path=policy_path)

    execute_calls = [str(call[0][0]) for call in mock_session.execute.call_args_list]
    assert any("pg_advisory_unlock" in s for s in execute_calls)


@pytest.mark.asyncio
async def test_do_ingest_reingests_when_chunker_version_changes():
    """_do_ingest should re-ingest when chunker_version differs even if source_hash is unchanged."""
    policy_path = "/tmp/policy.md"
    source_hash = "samehash"

    session = _make_session()

    policy = MagicMock()
    policy.policy_id = "policy-1"

    active_version = MagicMock()
    active_version.source_hash = source_hash
    active_version.embedding_model = "text-embedding-3-large"
    active_version.embedding_dim = 3072
    active_version.chunker_version = "v1"
    active_version.chunk_size = 600
    active_version.overlap = 100
    active_version.retrieval_schema_version = "v1"

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = policy
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = active_version
    result3 = MagicMock()
    result4 = MagicMock()

    session.execute.side_effect = [result1, result2, result3, result4]

    with (
        patch("app.rag.ingest.chunk_policy_document") as mock_chunk,
        patch("app.rag.ingest.EmbeddingFactory") as mock_factory,
        patch("app.rag.ingest.get_vector_store") as mock_store,
        patch("app.rag.ingest._validate_embedding"),
        patch("app.rag.ingest.datetime") as mock_dt,
    ):
        mock_chunk.return_value = [
            {"text": "chunk 1", "metadata": {}},
        ]
        mock_embed_fn = AsyncMock(return_value=[[0.0] * 1536])
        mock_factory.get_embedding_function.return_value = mock_embed_fn
        mock_store.return_value.upsert = AsyncMock()
        mock_dt.now.return_value = MagicMock()

        with patch("app.rag.ingest._get_embedding_dim", return_value=1536):
            result = await _do_ingest(session, policy_path, source_hash)

    assert result == 1
    assert session.add.call_count >= 1


@pytest.mark.asyncio
async def test_do_ingest_skips_when_snapshot_stable():
    """_do_ingest should skip when all snapshot fields are unchanged."""
    policy_path = "/tmp/policy.md"
    source_hash = "samehash"

    session = _make_session()

    policy = MagicMock()
    policy.policy_id = "policy-1"

    active_version = MagicMock()
    active_version.source_hash = source_hash
    active_version.embedding_model = "text-embedding-3-small"
    active_version.embedding_dim = 1536
    active_version.chunker_version = "v1"
    active_version.chunk_size = 600
    active_version.overlap = 100
    active_version.retrieval_schema_version = "v1"

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = policy
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = active_version

    session.execute.side_effect = [result1, result2]

    with patch("app.rag.ingest.get_vector_store") as mock_store:
        mock_store.return_value.count = AsyncMock(return_value=5)

        with patch("app.rag.ingest._get_embedding_dim", return_value=1536):
            result = await _do_ingest(session, policy_path, source_hash)

    assert result == 5


@pytest.mark.asyncio
async def test_do_ingest_reingests_when_embedding_model_changes():
    """_do_ingest should re-ingest when embedding_model differs in snapshot."""
    policy_path = "/tmp/policy.md"
    source_hash = "samehash"

    session = _make_session()

    policy = MagicMock()
    policy.policy_id = "policy-1"

    active_version = MagicMock()
    active_version.source_hash = source_hash
    active_version.embedding_model = "text-embedding-3-large"
    active_version.embedding_dim = 3072
    active_version.chunker_version = "v1"
    active_version.chunk_size = 600
    active_version.overlap = 100
    active_version.retrieval_schema_version = "v1"

    result1 = MagicMock()
    result1.scalar_one_or_none.return_value = policy
    result2 = MagicMock()
    result2.scalar_one_or_none.return_value = active_version
    result3 = MagicMock()
    result4 = MagicMock()

    session.execute.side_effect = [result1, result2, result3, result4]

    with (
        patch("app.rag.ingest.chunk_policy_document") as mock_chunk,
        patch("app.rag.ingest.EmbeddingFactory") as mock_factory,
        patch("app.rag.ingest.get_vector_store") as mock_store,
        patch("app.rag.ingest._validate_embedding"),
        patch("app.rag.ingest.datetime") as mock_dt,
    ):
        mock_chunk.return_value = [
            {"text": "chunk 1", "metadata": {}},
        ]
        mock_embed_fn = AsyncMock(return_value=[[0.0] * 1536])
        mock_factory.get_embedding_function.return_value = mock_embed_fn
        mock_store.return_value.upsert = AsyncMock()
        mock_dt.now.return_value = MagicMock()

        with patch("app.rag.ingest._get_embedding_dim", return_value=1536):
            result = await _do_ingest(session, policy_path, source_hash)

    assert result == 1
    assert session.add.call_count >= 1
