"""Coverage tests for app.rag.claims_rag uncovered paths."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestClaimsRag:
    @pytest.mark.asyncio
    async def test_retrieve_claims_hybrid_exception_returns_empty(self):
        from app.rag.claims_rag import retrieve_claims_hybrid

        with patch("app.rag.claims_rag.get_vector_store") as mock_get:
            mock_store = MagicMock()
            mock_store.hybrid_search = AsyncMock(side_effect=Exception("search failed"))
            mock_get.return_value = mock_store
            result = await retrieve_claims_hybrid(
                query="test",
                user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            )
        assert result == []
