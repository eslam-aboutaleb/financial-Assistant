"""
Unit tests for the RAG ingestion and hybrid retrieval modules using the vector store abstraction.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rag.claims_rag import ingest_all_claims, ingest_claim, retrieve_claims_hybrid
from app.rag.embedding import EmbeddingFactory, LitellmEmbeddingFunction
from app.rag.ingest import chunk_policy_document, ingest_policy
from app.rag.retriever import retrieve_hybrid


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
            mock_embed.return_value = AsyncMock(return_value=[[0.1] * 1536 for _ in ["test"]])
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
        mock_embed.return_value = AsyncMock(return_value=[[0.1] * 1536])
        res = await retrieve_hybrid("test")
        assert len(res) == 1
        assert res[0]["document"] == "mock document"
        assert res[0]["distance"] == 0.5


@pytest.mark.asyncio
async def test_embedding_factory():
    fn = EmbeddingFactory.get_embedding_function()
    assert isinstance(fn, LitellmEmbeddingFunction)
    res = await fn(["test 1", "test 2"])
    assert len(res) == 2
    assert len(res[0]) == 1536


@pytest.mark.asyncio
async def test_embedding_function_embed_query():
    fn = EmbeddingFactory.get_embedding_function()
    result = await fn.embed_query("test query")
    assert len(result) == 1536


@pytest.mark.asyncio
async def test_embedding_function_embed_documents():
    fn = EmbeddingFactory.get_embedding_function()
    result = await fn.embed_documents(["doc1", "doc2"])
    assert len(result) == 2
    assert len(result[0]) == 1536


@pytest.mark.asyncio
async def test_ingest_policy_skip_if_exists():
    mock_store = AsyncMock()
    mock_store.count.return_value = 10

    with (
        patch("app.rag.ingest.get_vector_store", return_value=mock_store),
        patch("app.rag.ingest.async_session_factory") as mock_factory,
        patch("app.rag.ingest.hashlib.sha256") as mock_sha,
    ):
        mock_sha.return_value.hexdigest.return_value = "storedhash"
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = {"source_hash": "storedhash"}
        mock_session.execute.return_value = mock_result
        mock_factory.return_value.__aenter__.return_value = mock_session

        count = await ingest_policy()
        assert count == 10
        mock_store.count.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_policy_no_chunks():
    mock_store = AsyncMock()

    with (
        patch("app.rag.ingest.get_vector_store", return_value=mock_store),
        patch("app.rag.ingest.chunk_policy_document", return_value=[]),
        patch("app.rag.ingest.async_session_factory") as mock_factory,
        patch("app.rag.ingest.hashlib.sha256") as mock_sha,
    ):
        mock_sha.return_value.hexdigest.return_value = "newhash"
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = {"source_hash": "oldhash"}
        mock_session.execute.return_value = mock_result
        mock_factory.return_value.__aenter__.return_value = mock_session

        count = await ingest_policy()
        assert count == 0
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
        patch("app.rag.ingest.async_session_factory") as mock_factory,
        patch("app.rag.ingest.hashlib.sha256") as mock_sha,
    ):
        mock_sha.return_value.hexdigest.return_value = "newhash"
        mock_embed.return_value = AsyncMock(return_value=[[0.1] * 1536 for _ in chunks])
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.first.return_value = None
        mock_session.execute.return_value = mock_result
        mock_factory.return_value.__aenter__.return_value = mock_session

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
        mock_embed.return_value = AsyncMock(return_value=[[0.1] * 1536])
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
            mock_embed.return_value = AsyncMock(return_value=[[0.1] * 1536])
            error_results = await retrieve_claims_hybrid("kitchen", test_user_id)
            assert error_results == []


@pytest.mark.asyncio
async def test_ingest_claim():
    test_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    test_user_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
    mock_store = AsyncMock()

    with (
        patch("app.rag.claims_rag.get_vector_store", return_value=mock_store),
        patch("app.rag.claims_rag.EmbeddingFactory.get_embedding_function") as mock_embed,
    ):
        mock_embed.return_value = AsyncMock(return_value=[[0.1] * 1536])
        await ingest_claim(
            id=test_id,
            claim_id="CLM-1",
            owner_id=test_user_id,
            claim_type="Water",
            description="Pipe burst",
            policy_number="POL-1",
            status="Open",
            amount=1000.0,
        )
        mock_store.upsert.assert_called_once()
        call_docs = mock_store.upsert.call_args[1]["documents"]
        assert call_docs[0]["id"] == str(test_id)
        assert call_docs[0]["metadata"]["claim_id"] == "CLM-1"


@pytest.mark.asyncio
async def test_ingest_all_claims():
    mock_claim = MagicMock()
    mock_claim.id = uuid.UUID("00000000-0000-0000-0000-000000000001")
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
            call_kwargs = mock_ingest.call_args[1]
            assert call_kwargs["id"] == mock_claim.id
            assert call_kwargs["claim_id"] == mock_claim.claim_id


# --- Defect 3: Policy ingestion re-ingests when file hash changes ---


@pytest.mark.asyncio
async def test_ingest_policy_reingests_when_hash_changes(tmp_path):
    """ingest_policy() re-ingests when the source file hash differs."""
    md_file = tmp_path / "policy.md"
    md_file.write_text("# Policy\n\nOriginal content.", encoding="utf-8")

    mock_store = AsyncMock()
    mock_store.count.return_value = 2

    with (
        patch("app.rag.ingest.get_vector_store", return_value=mock_store),
        patch("app.rag.ingest.chunk_policy_document") as mock_chunk,
        patch("app.rag.ingest.EmbeddingFactory.get_embedding_function") as mock_embed,
        patch("app.rag.ingest.async_session_factory") as mock_session_factory,
        patch("app.rag.ingest.hashlib.sha256") as mock_sha,
    ):
        mock_sha.return_value.hexdigest.return_value = "originalhash"
        mock_chunk.return_value = [
            {"id": "c1", "text": "Policy text", "metadata": {"source": "policy.md"}}
        ]
        mock_embed.return_value = AsyncMock(return_value=[[0.1] * 1536])
        mock_session = AsyncMock()
        mock_execute_result = MagicMock()
        mock_execute_result.mappings.return_value.first.return_value = None
        mock_session.execute.return_value = mock_execute_result
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        # First call: no stored hash, should ingest.
        count1 = await ingest_policy(policy_path=str(md_file))
        assert count1 == 1
        mock_store.upsert.assert_called_once()

        # Reset mock for second call.
        mock_store.reset_mock()
        mock_execute_result.mappings.return_value.first.return_value = {
            "source_hash": "originalhash"
        }

        # Second call: hash matches stored, should skip.
        count2 = await ingest_policy(policy_path=str(md_file))
        assert count2 == 2
        mock_store.upsert.assert_not_called()

        # Update file content to trigger re-ingestion.
        md_file.write_text("# Policy\n\nChanged content.", encoding="utf-8")
        mock_sha.return_value.hexdigest.return_value = "changedhash"
        mock_chunk.return_value = [
            {"id": "c2", "text": "Changed Policy text", "metadata": {"source": "policy.md"}}
        ]
        mock_embed.return_value = AsyncMock(return_value=[[0.2] * 1536])
        mock_execute_result.mappings.return_value.first.return_value = {
            "source_hash": "originalhash"
        }

        # Third call: hash differs, should re-ingest.
        count3 = await ingest_policy(policy_path=str(md_file))
        assert count3 == 1
        mock_store.upsert.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_policy_skips_missing_file():
    """ingest_policy() returns 0 and does not crash when file is missing."""
    mock_store = AsyncMock()

    with patch("app.rag.ingest.get_vector_store", return_value=mock_store):
        count = await ingest_policy(policy_path="/nonexistent/path/policy.md")
        assert count == 0
        mock_store.upsert.assert_not_called()


# --- Defect 2: submit_claim_internal enqueues EmbeddingJob ---


@pytest.mark.asyncio
async def test_submit_claim_internal_enqueues_embedding_job():
    """submit_claim_internal() enqueues an EmbeddingJob with the correct claim_uuid."""
    from app.agent.tools.submit_claim import submit_claim_internal
    from app.agent.context import current_user_id

    user_uuid = uuid.UUID("00000000-0000-0000-0000-000000000003")
    current_user_id.set(user_uuid)

    new_claim = MagicMock()
    new_claim.id = uuid.UUID("00000000-0000-0000-0000-000000000004")
    new_claim.claim_id = "CLM-TEST"
    new_claim.owner_id = user_uuid
    new_claim.claim_type = "Water Damage"
    new_claim.description = "Pipe burst"
    new_claim.policy_number = "POL-1092"
    new_claim.status = "Submitted"
    new_claim.amount = 1500.0

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    fixed_uuid = uuid.UUID("00000000-0000-0000-0000-000000000004")

    with (
        patch("app.agent.tools.submit_claim.async_session_factory") as mock_factory,
        patch(
            "app.agent.tools.submit_claim.enqueue_embedding_job", new_callable=AsyncMock
        ) as mock_enqueue,
        patch("app.agent.tools.submit_claim.uuid.uuid4", return_value=fixed_uuid),
    ):
        mock_factory.return_value.__aenter__.return_value = mock_session

        # Patch Claim constructor to return our mock
        with patch("app.agent.tools.submit_claim.Claim", return_value=new_claim):
            result = await submit_claim_internal(
                policy_number="POL-1092",
                claim_type="Water Damage",
                amount=1500.0,
                description="Pipe burst",
                user_uuid=user_uuid,
            )

    assert result["success"] is True
    assert result["confirmation_id"] == "CLM-00000000"
    mock_enqueue.assert_called_once()
    call_kwargs = mock_enqueue.call_args[1]
    assert call_kwargs["claim_uuid"] == new_claim.id
    assert call_kwargs["claim_id"] == "CLM-TEST"
    assert call_kwargs["owner_id"] == user_uuid
    assert call_kwargs["claim_type"] == "Water Damage"
