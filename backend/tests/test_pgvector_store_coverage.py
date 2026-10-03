"""Coverage tests for app.rag.pgvector_store uncovered paths."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestPgVectorStore:
    def test_validate_identifier_unsafe_name(self):
        from app.rag.pgvector_store import _validate_identifier

        with pytest.raises(ValueError, match="Unsafe"):
            _validate_identifier("bad-name", "label")

    def test_validate_embedding_wrong_dimension(self):
        from app.rag.pgvector_store import _validate_embedding

        with pytest.raises(ValueError, match="has 2 dimensions"):
            _validate_embedding([1.0, 2.0], expected_dim=1536)

    def test_validate_embedding_non_finite_values(self):
        from app.rag.pgvector_store import _validate_embedding

        with pytest.raises(ValueError, match="not finite"):
            _validate_embedding([1.0, float("nan"), 3.0], expected_dim=3)

    def test_validate_embedding_non_numeric_value(self):
        from app.rag.pgvector_store import _validate_embedding

        with pytest.raises(TypeError, match="not a number"):
            _validate_embedding(["a", "b"], expected_dim=2)

    @pytest.mark.asyncio
    async def test_hybrid_search_exception_returns_empty(self):
        from app.rag.pgvector_store import PgVectorStore

        store = PgVectorStore(table_name="policy_chunks", id_field="id", embedding_dim=1536)
        with patch("app.rag.pgvector_store.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__.side_effect = Exception("DB down")
            result = await store.hybrid_search(
                query="test", embedding=[0.0] * 1536, n_results=5, threshold=1.0
            )
        assert result == []

    @pytest.mark.asyncio
    async def test_count_with_external_session(self):
        from app.rag.pgvector_store import PgVectorStore

        store = PgVectorStore(table_name="policy_chunks", id_field="id", embedding_dim=1536)
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 42
        mock_session.execute.return_value = mock_result
        count = await store.count(session=mock_session)
        assert count == 42

    def test_upsert_metadata_key_validation(self):
        from app.rag.pgvector_store import PgVectorStore

        store = PgVectorStore(table_name="policy_chunks", id_field="id", embedding_dim=1536)
        with pytest.raises(ValueError, match="Unsafe"):
            asyncio.run(
                store.upsert(
                    documents=[
                        {
                            "id": "1",
                            "text": "test",
                            "embedding": [0.0] * 1536,
                            "metadata": {"bad-key": "value"},
                        }
                    ]
                )
            )

    @pytest.mark.asyncio
    async def test_upsert_external_session(self):
        from app.rag.pgvector_store import PgVectorStore

        store = PgVectorStore(table_name="policy_chunks", id_field="id", embedding_dim=1536)
        mock_session = AsyncMock()
        await store.upsert(
            documents=[{"id": "1", "text": "test", "embedding": [0.0] * 1536}],
            session=mock_session,
        )
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_exception_logged(self):
        from app.rag.pgvector_store import PgVectorStore

        store = PgVectorStore(table_name="policy_chunks", id_field="id", embedding_dim=1536)
        with patch("app.rag.pgvector_store.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__.side_effect = Exception("DB down")
            with pytest.raises(Exception, match="DB down"):
                await store.upsert(
                    documents=[{"id": "1", "text": "test", "embedding": [0.0] * 1536}]
                )

    def test_upsert_metadata_key_validation_in_loop(self):
        from app.rag.pgvector_store import PgVectorStore

        store = PgVectorStore(table_name="policy_chunks", id_field="id", embedding_dim=1536)
        with pytest.raises(ValueError, match="Unsafe"):
            asyncio.run(
                store.upsert(
                    documents=[
                        {
                            "id": "1",
                            "text": "test",
                            "embedding": [0.0] * 1536,
                            "metadata": {"bad-key": "value", "another-bad": "x"},
                        }
                    ]
                )
            )

    def test_upsert_with_extra_fields(self):
        from app.rag.pgvector_store import PgVectorStore

        store = PgVectorStore(table_name="policy_chunks", id_field="id", embedding_dim=1536)
        with patch("app.rag.pgvector_store.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_factory.return_value.__aenter__.return_value = mock_session
            asyncio.run(
                store.upsert(
                    documents=[
                        {
                            "id": "1",
                            "text": "test",
                            "embedding": [0.0] * 1536,
                            "metadata": {"section": "Section 1"},
                        }
                    ],
                    extra_fields={"owner_id": "user-1"},
                )
            )
            mock_session.execute.assert_called_once()
