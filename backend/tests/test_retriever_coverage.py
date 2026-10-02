"""Coverage tests for app.rag.retriever uncovered paths."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestRetriever:
    @pytest.mark.asyncio
    async def test_retrieve_hybrid_exception_returns_empty(self):
        from app.rag.retriever import retrieve_hybrid

        with patch("app.rag.retriever.get_vector_store") as mock_get:
            mock_store = MagicMock()
            mock_store.hybrid_search = AsyncMock(side_effect=Exception("search failed"))
            mock_get.return_value = mock_store
            result = await retrieve_hybrid(query="test", n_results=5)
        assert result == []
