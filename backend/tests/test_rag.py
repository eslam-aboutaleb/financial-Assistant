"""
Unit tests for the RAG ingestion and hybrid retrieval modules using the vector store abstraction.
"""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.rag.ingest import chunk_policy_document, ingest_policy
from app.rag.retriever import retrieve_hybrid
from app.rag.claims_rag import retrieve_claims_hybrid, ingest_claim, ingest_all_claims
from app.rag.embedding import EmbeddingFactory, LitellmEmbeddingFunction


def test_chunk_policy_document(tmp_path):
    md_file = tmp_path / "test.md"
    md_file.write_text(
        "## Section 1\n\nThis is a test policy.\n\n## Section 2\n\nAnother section.",
        encoding="utf-8",
    )
    chunks = chunk_policy_document(str(md_file))
    assert len(chunks) >= 2
    assert chunks[0]["metadata"]["section"] == "Section 1"
    assert "test policy" in chunks[0]["text"].lower()


@pytest.mark.asyncio
async def test_retrieve_hybrid_exception():
    with patch("app.rag.retriever.get_vector_store") as mock_factory:
        mock_store = AsyncMock()
        mock_factory.return_value = mock_store
        mock_store.hybrid_search.side_effect = Exception("DB error")

        with patch("app.rag.retriever.EmbeddingFactory.get_embedding_function") as mock_embed:
            mock_embed.return_value = lambda x: [[0.1] * 1536 for _ in x]
            res = await retrieve_hybrid("test")
            assert res == []


@pytest.mark.asyncio
async def test_retrieve_hybrid_success():
    mock_store = AsyncMock()
    mock_store.hybrid_search.return_value = [
        {
            "document": "mock document",
            "metadata": {
                "section": "Mock Section",
                "source": "mock.md",
                "chunk_index": 0,
                "sub_chunk_index": 0,
            },
            "distance": 0.5,
            "_rrf_score": 0.8,
        }
    ]

    with (
        patch("app.rag.retriever.get_vector_store", return_value=mock_store),
        patch("app.rag.retriever.EmbeddingFactory.get_embedding_function") as mock_embed,
    ):
        mock_embed.return_value = lambda x: [[0.1] * 1536 for _ in x]
        res = await retrieve_hybrid("test")
        assert len(res) == 1
        assert res[0]["document"] == "mock document"
        assert res[0]["distance"] == 0.5


def test_embedding_factory():
    fn = EmbeddingFactory.get_embedding_function()
    assert isinstance(fn, LitellmEmbeddingFunction)
    res = fn(["test 1", "test 2"])
    assert len(res) == 2
    assert len(res[0]) == 1536


def test_embedding_function_embed_query():
    fn = EmbeddingFactory.get_embedding_function()
    result = fn.embed_query("test query")
    assert len(result) == 1536


def test_embedding_function_embed_documents():
    fn = EmbeddingFactory.get_embedding_function()
    result = fn.embed_documents(["doc1", "doc2"])
    assert len(result) == 2
    assert len(result[0]) == 1536


@pytest.mark.asyncio
async def test_ingest_policy_skip_if_exists():
    mock_store = AsyncMock()
    mock_store.count.return_value = 10

    with patch("app.rag.ingest.get_vector_store", return_value=mock_store):
        count = await ingest_policy()
        assert count == 10
        mock_store.count.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_policy_no_chunks():
    mock_store = AsyncMock()
    mock_store.count.return_value = 0

    with (
        patch("app.rag.ingest.get_vector_store", return_value=mock_store),
        patch("app.rag.ingest.chunk_policy_document", return_value=[]),
    ):
        count = await ingest_policy()
        assert count == 0
        mock_store.count.assert_called_once()
        mock_store.upsert.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_policy_success():
    chunks = [
        {
            "id": "chunk_1",
            "text": "test policy text",
            "metadata": {
                "section": "Test",
                "source": "test.md",
                "chunk_index": 0,
                "sub_chunk_index": 0,
            },
        }
    ]
    mock_store = AsyncMock()
    mock_store.count.return_value = 0

    with (
        patch("app.rag.ingest.get_vector_store", return_value=mock_store),
        patch("app.rag.ingest.chunk_policy_document", return_value=chunks),
        patch("app.rag.ingest.EmbeddingFactory.get_embedding_function") as mock_embed,
    ):
        mock_embed.return_value = lambda x: [[0.1] * 1536 for _ in x]
        count = await ingest_policy()
        assert count == len(chunks)
        mock_store.upsert.assert_called_once()


# Claims RAG tests


@pytest.mark.asyncio
async def test_claims_rag_hybrid():
    test_user_id = uuid.uuid4()

    mock_store = AsyncMock()
    mock_store.hybrid_search.return_value = [
        {
            "document": "Claim TEST-123: Water Damage - Pipe burst",
            "metadata": {
                "claim_id": "TEST-123",
                "policy_number": "POL-123",
                "claim_type": "Water Damage",
                "status": "Pending",
                "amount": 1500.0,
            },
            "distance": 0.5,
            "_rrf_score": 0.8,
        }
    ]

    with (
        patch("app.rag.claims_rag.get_vector_store", return_value=mock_store),
        patch("app.rag.claims_rag.EmbeddingFactory.get_embedding_function") as mock_embed,
    ):
        mock_embed.return_value = lambda x: [[0.1] * 1536 for _ in x]
        results = await retrieve_claims_hybrid("kitchen pipe", test_user_id)
        assert len(results) > 0
        assert results[0]["metadata"]["claim_id"] == "TEST-123"
        mock_store.hybrid_search.assert_called_once()


@pytest.mark.asyncio
async def test_claims_rag_exception_handling():
    test_user_id = uuid.uuid4()

    with patch("app.rag.claims_rag.get_vector_store") as mock_factory:
        mock_store = AsyncMock()
        mock_factory.return_value = mock_store
        mock_store.hybrid_search.side_effect = Exception("DB error")

        with patch("app.rag.claims_rag.EmbeddingFactory.get_embedding_function") as mock_embed:
            mock_embed.return_value = lambda x: [[0.1] * 1536 for _ in x]
            error_results = await retrieve_claims_hybrid("kitchen", test_user_id)
            assert error_results == []


@pytest.mark.asyncio
async def test_ingest_claim():
    test_user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    mock_store = AsyncMock()

    with (
        patch("app.rag.claims_rag.get_vector_store", return_value=mock_store),
        patch("app.rag.claims_rag.EmbeddingFactory.get_embedding_function") as mock_embed,
    ):
        mock_embed.return_value = lambda x: [[0.1] * 1536 for _ in x]
        await ingest_claim(
            claim_id="CLM-1",
            owner_id=test_user_id,
            claim_type="Water",
            description="Pipe burst",
            policy_number="POL-1",
            status="Open",
            amount=1000.0,
        )
        mock_store.upsert.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_all_claims():
    mock_claim = MagicMock()
    mock_claim.claim_id = "CLM-1"
    mock_claim.owner_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    mock_claim.claim_type = "Water"
    mock_claim.description = "Pipe burst"
    mock_claim.policy_number = "POL-1"
    mock_claim.status = "Open"
    mock_claim.amount = 1000.0

    with patch("app.rag.claims_rag.async_session_factory") as mock_factory:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_claim]
        mock_session.execute.return_value = mock_result
        mock_factory.return_value.__aenter__.return_value = mock_session

        with patch("app.rag.claims_rag.ingest_claim", new_callable=AsyncMock) as mock_ingest:
            await ingest_all_claims()
            mock_ingest.assert_called_once()
