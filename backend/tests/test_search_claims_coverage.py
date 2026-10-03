"""Coverage tests for app.agent.tools.search_claims uncovered paths."""

from __future__ import annotations

from unittest.mock import patch

import pytest


class TestSearchClaimsTool:
    @pytest.mark.asyncio
    async def test_search_claims_returns_empty_on_no_context(self):
        from app.agent.tools.search_claims import search_claims

        with patch("app.agent.context.current_user_id") as mock_cv:
            mock_cv.get.side_effect = LookupError
            result = await search_claims(query="claim")
            assert result == [{"error": "Unauthorized claim search."}]
