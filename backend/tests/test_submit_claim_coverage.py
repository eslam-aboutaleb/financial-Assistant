"""Coverage tests for app.agent.tools.submit_claim uncovered paths."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest


class TestSubmitClaimTool:
    @pytest.mark.asyncio
    async def test_prepare_claim_submission_returns_error_on_exception(self):
        from app.agent.context import current_user_id
        from app.agent.tools.submit_claim import prepare_claim_submission

        current_user_id.set(uuid.uuid4())
        with patch("app.agent.tools.submit_claim.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__.side_effect = Exception("DB down")
            result = await prepare_claim_submission(
                policy_number="POL-1092",
                claim_type="Water Damage",
                amount=2500.0,
                description="Frozen pipe burst causing water damage to hardwood floors",
            )
            assert result.get("success") is False
            assert "could not be prepared" in result["error"]

    @pytest.mark.asyncio
    async def test_submit_claim_internal_validation_error(self):
        from app.agent.tools.submit_claim import submit_claim_internal

        result = await submit_claim_internal(
            policy_number="POL-1092",
            claim_type="Water Damage",
            amount=-5.0,
            description="short",
            user_uuid=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        )
        assert result.get("success") is False
        assert "validation_errors" in result
