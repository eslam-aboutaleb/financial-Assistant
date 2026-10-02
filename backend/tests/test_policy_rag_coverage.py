"""Coverage tests for app.agent.tools.policy_rag uncovered paths."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


class TestPolicyRagTool:
    @pytest.mark.asyncio
    async def test_query_policy_returns_empty_on_no_context(self):
        from app.agent.tools.policy_rag import query_policy

        with patch("app.agent.tools.policy_rag.retrieve_hybrid", new_callable=AsyncMock) as mock_retrieve:
            mock_retrieve.return_value = []
            result = await query_policy(query="coverage")
            assert result.get("chunks_found") == 0
