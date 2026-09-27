import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.tools.submit_claim import prepare_claim_submission


@pytest.mark.asyncio
async def test_prepare_claim_submission_success():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    with (
        patch("app.agent.tools.submit_claim.async_session_factory") as mock_factory,
    ):
        mock_factory.return_value.__aenter__.return_value = mock_session

        from app.agent.context import current_user_id

        current_user_id.set(uuid.uuid4())

        result = await prepare_claim_submission(
            policy_number="POL-1092",
            claim_type="Water Damage",
            amount=2500.00,
            description="Frozen pipe burst causing water damage to hardwood floors",
        )

        assert "error" not in result
        assert result.get("success") is True
        assert "confirmation_token" in result
        assert result["status"] == "pending"


@pytest.mark.asyncio
async def test_prepare_claim_submission_invalid_negative_amount():
    from app.agent.context import current_user_id

    current_user_id.set(uuid.uuid4())
    result = await prepare_claim_submission(
        policy_number="POL-1092",
        claim_type="Water Damage",
        amount=-500.00,
        description="Negative amount",
    )
    assert result.get("success") is False
    assert "validation_errors" in result


@pytest.mark.asyncio
async def test_prepare_claim_submission_short_description():
    from app.agent.context import current_user_id

    current_user_id.set(uuid.uuid4())
    result = await prepare_claim_submission(
        policy_number="POL-1092", claim_type="Water Damage", amount=150.00, description="Too short"
    )
    assert result.get("success") is False
    assert "validation_errors" in result
