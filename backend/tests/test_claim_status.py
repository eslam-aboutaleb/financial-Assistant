import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.agent.tools.claim_status import get_claim_status
from app.agent.context import current_user_id
import uuid

@pytest.mark.asyncio
async def test_get_claim_status_success():
    current_user_id.set(uuid.uuid4())
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_claim = MagicMock()
    mock_claim.claim_id = "CLM-1234"
    mock_claim.status = "Approved"
    mock_claim.amount = 500.0
    mock_claim.description = "Test claim"
    
    mock_result.scalar_one_or_none.return_value = mock_claim
    mock_session.execute.return_value = mock_result
    
    with patch("app.agent.tools.claim_status.async_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__.return_value = mock_session
        
        result = await get_claim_status(claim_id="CLM-1234")
        
        assert result["found"] is True
        assert result["status"] == "Approved"

@pytest.mark.asyncio
async def test_get_claim_status_not_found():
    current_user_id.set(uuid.uuid4())
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result
    
    with patch("app.agent.tools.claim_status.async_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__.return_value = mock_session
        
        result = await get_claim_status(claim_id="CLM-9999")
        
        assert result["found"] is False
        assert "no claim found" in result["error"].lower()
