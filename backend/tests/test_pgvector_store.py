"""
Additional tests for pgvector_store edge cases.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.rag.pgvector_store import PgVectorStore


@pytest.mark.asyncio
async def test_hybrid_search_with_empty_embedding():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_row = MagicMock()
    mock_row.__getitem__ = lambda self, key: {
        "id": "1",
        "document": "test doc",
        "section": "Test",
        "source": "test.md",
        "chunk_index": 0,
        "sub_chunk_index": 0,
        "distance": 0.5,
        "rrf_score": 0.8,
    }[key]
    mock_result.mappings.return_value.all.return_value = [mock_row]
    mock_session.execute.return_value = mock_result

    store = PgVectorStore(table_name="policy_chunks", id_field="id")

    with patch("app.rag.pgvector_store.async_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__.return_value = mock_session
        with patch("app.rag.pgvector_store.EmbeddingFactory.get_embedding_function") as mock_embed:
            mock_embed.return_value = lambda x: [[0.1] * 1536 for _ in x]
            result = await store.hybrid_search(
                query="test",
                embedding=[],
                n_results=5,
                threshold=1.3,
                text_field="text",
                metadata_fields=["section", "source"],
            )
            assert len(result) == 1
            assert result[0]["document"] == "test doc"


@pytest.mark.asyncio
async def test_hybrid_search_with_extra_where():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_row = MagicMock()
    mock_row.__getitem__ = lambda self, key: {
        "id": "1",
        "document": "test doc",
        "distance": 0.5,
        "rrf_score": 0.8,
    }[key]
    mock_result.mappings.return_value.all.return_value = [mock_row]
    mock_session.execute.return_value = mock_result

    store = PgVectorStore(table_name="claims", id_field="id")

    with patch("app.rag.pgvector_store.async_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__.return_value = mock_session
        with patch("app.rag.pgvector_store.EmbeddingFactory.get_embedding_function") as mock_embed:
            mock_embed.return_value = lambda x: [[0.1] * 1536 for _ in x]
            result = await store.hybrid_search(
                query="test",
                embedding=[0.1] * 1536,
                n_results=5,
                threshold=1.3,
                text_field="description",
                metadata_fields=["claim_id"],
                extra_where="owner_id = :owner_id",
                extra_params={"owner_id": "user-123"},
            )
            assert len(result) == 1


@pytest.mark.asyncio
async def test_count_with_extra_where():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 5
    mock_session.execute.return_value = mock_result

    store = PgVectorStore(table_name="claims", id_field="id")

    with patch("app.rag.pgvector_store.async_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__.return_value = mock_session
        count = await store.count(
            extra_where="owner_id = :owner_id", extra_params={"owner_id": "user-123"}
        )
        assert count == 5


@pytest.mark.asyncio
async def test_hybrid_search_with_empty_metadata_fields():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_row = MagicMock()
    mock_row.__getitem__ = lambda self, key: {
        "id": "1",
        "document": "test doc",
        "distance": 0.5,
        "rrf_score": 0.8,
    }[key]
    mock_result.mappings.return_value.all.return_value = [mock_row]
    mock_session.execute.return_value = mock_result

    store = PgVectorStore(table_name="policy_chunks", id_field="id")

    with patch("app.rag.pgvector_store.async_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__.return_value = mock_session
        with patch("app.rag.pgvector_store.EmbeddingFactory.get_embedding_function") as mock_embed:
            mock_embed.return_value = lambda x: [[0.1] * 1536 for _ in x]
            result = await store.hybrid_search(
                query="test",
                embedding=[0.1] * 1536,
                n_results=5,
                threshold=1.3,
                text_field="text",
                metadata_fields=[],
            )
            assert len(result) == 1
            assert result[0]["metadata"] == {}


@pytest.mark.asyncio
async def test_count_without_extra_where():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 10
    mock_session.execute.return_value = mock_result

    store = PgVectorStore(table_name="policy_chunks", id_field="id")

    with patch("app.rag.pgvector_store.async_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__.return_value = mock_session
        count = await store.count()
        assert count == 10


@pytest.mark.asyncio
async def test_hybrid_search_metadata_field_populated():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_row = MagicMock()
    mock_row.__getitem__ = lambda self, key: {
        "id": "1",
        "document": "test doc",
        "section": "Test Section",
        "source": "test.md",
        "chunk_index": 0,
        "sub_chunk_index": 0,
        "distance": 0.5,
        "rrf_score": 0.8,
    }[key]
    mock_row.__contains__ = lambda self, key: (
        key
        in {
            "id",
            "document",
            "section",
            "source",
            "chunk_index",
            "sub_chunk_index",
            "distance",
            "rrf_score",
        }
    )
    mock_result.mappings.return_value.all.return_value = [mock_row]
    mock_session.execute.return_value = mock_result

    store = PgVectorStore(table_name="policy_chunks", id_field="id")

    with patch("app.rag.pgvector_store.async_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__.return_value = mock_session
        with patch("app.rag.pgvector_store.EmbeddingFactory.get_embedding_function") as mock_embed:
            mock_embed.return_value = lambda x: [[0.1] * 1536 for _ in x]
            result = await store.hybrid_search(
                query="test",
                embedding=[0.1] * 1536,
                n_results=5,
                threshold=1.3,
                text_field="text",
                metadata_fields=["section", "source"],
            )
            assert len(result) == 1
            assert result[0]["metadata"]["section"] == "Test Section"
            assert result[0]["metadata"]["source"] == "test.md"


@pytest.mark.asyncio
async def test_count_exception_handling():
    store = PgVectorStore(table_name="policy_chunks", id_field="id")

    with patch("app.rag.pgvector_store.async_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__.side_effect = Exception("DB error")
        count = await store.count()
        assert count == 0


@pytest.mark.asyncio
async def test_upsert_with_empty_documents():
    store = PgVectorStore(table_name="policy_chunks", id_field="id")

    with patch("app.rag.pgvector_store.async_session_factory") as mock_factory:
        await store.upsert([])
        mock_factory.return_value.__aenter__.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_with_extra_fields():
    mock_session = AsyncMock()
    mock_session.execute.return_value = None

    store = PgVectorStore(table_name="claims", id_field="id")

    with patch("app.rag.pgvector_store.async_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__.return_value = mock_session
        await store.upsert(
            documents=[
                {
                    "id": "claim-1",
                    "text": "test claim",
                    "embedding": [0.1] * 1536,
                    "claim_id": "CLM-1",
                    "owner_id": "user-123",
                }
            ],
            extra_fields={"status": "Pending"},
        )
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_upsert_commits_transactions():
    mock_session = AsyncMock()
    mock_session.execute.return_value = None

    store = PgVectorStore(table_name="policy_chunks", id_field="id")

    with patch("app.rag.pgvector_store.async_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__.return_value = mock_session
        await store.upsert(
            documents=[
                {
                    "id": "chunk-1",
                    "text": "test chunk",
                    "embedding": [0.1] * 1536,
                }
            ]
        )
        mock_session.commit.assert_called_once()
