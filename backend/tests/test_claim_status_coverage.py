"""Coverage tests for app.agent.tools.claim_status uncovered paths."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest


class TestClaimStatusTool:
    @pytest.mark.asyncio
    async def test_get_claim_status_returns_unauthorized_when_no_context(self):
        from app.agent.tools.claim_status import get_claim_status

        with patch("app.agent.tools.claim_status.current_user_id") as mock_cv:
            mock_cv.get.side_effect = LookupError
            result = await get_claim_status(claim_id="CLM-9999")
            assert result["found"] is False
            assert "Unauthorized" in result["error"]

    @pytest.mark.asyncio
    async def test_get_claim_status_returns_error_on_exception(self):
        from app.agent.tools.claim_status import get_claim_status

        with patch("app.agent.tools.claim_status.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__.side_effect = Exception("DB down")
            with patch("app.agent.tools.claim_status.current_user_id") as mock_cv:
                mock_cv.get.return_value = uuid.UUID("00000000-0000-0000-0000-000000000001")
                result = await get_claim_status(claim_id="CLM-9999")
                assert result["found"] is False
                assert "Unable to retrieve" in result["error"]
