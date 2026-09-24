"""
Direct unit tests for the claim_status tool function.

Tests:
- test_get_existing_claim_8821: Call get_claim_status('CLM-8821') with mock claims data,
  verify returns Approved status
- test_get_existing_claim_9014: Call get_claim_status('CLM-9014'), verify returns Under Review
- test_get_nonexistent_claim: Call with 'CLM-0000', verify returns error message
- test_claim_response_has_all_fields: Verify response includes claim_id, policy_number,
  claim_type, status, amount
"""

from app.agent.tools.claim_status import get_claim_status


def test_get_existing_claim_8821(sample_claims_path):
    """
    Test looking up existing claim 'CLM-8821'.
    Verifies that the status is 'Approved' and fields match baseline data.
    """
    result = get_claim_status("CLM-8821")

    assert "error" not in result, f"Unexpected error returned: {result}"
    assert result["claim_id"] == "CLM-8821"
    assert result["policy_number"] == "POL-1092"
    assert result["claim_type"] == "Water Damage"
    assert result["status"] == "Approved"
    assert result["amount"] == 3500.00


def test_get_existing_claim_9014(sample_claims_path):
    """
    Test looking up existing claim 'CLM-9014'.
    Verifies that the status is 'Under Review' and fields match baseline data.
    """
    result = get_claim_status("CLM-9014")

    assert "error" not in result, f"Unexpected error returned: {result}"
    assert result["claim_id"] == "CLM-9014"
    assert result["policy_number"] == "POL-3341"
    assert result["claim_type"] == "Personal Property"
    assert result["status"] == "Under Review"
    assert result["amount"] == 1200.00


def test_get_nonexistent_claim(sample_claims_path):
    """
    Test looking up a nonexistent claim 'CLM-0000'.
    Verifies that an error message is returned and no claim data is exposed.
    """
    result = get_claim_status("CLM-0000")

    assert "error" in result, f"Expected 'error' in response for nonexistent claim, got {result}"
    assert "No claim found" in result["error"]
    assert "CLM-0000" in result["error"]


def test_claim_response_has_all_fields(sample_claims_path):
    """
    Test that the returned claim response contains all expected fields:
    claim_id, policy_number, claim_type, status, amount.
    """
    result = get_claim_status("CLM-8821")

    assert "error" not in result

    expected_fields = {"claim_id", "policy_number", "claim_type", "status", "amount"}
    actual_fields = set(result.keys())

    missing = expected_fields - actual_fields
    assert not missing, f"Missing expected fields in claim response: {missing}"

    # Verify types of the returned fields
    assert isinstance(result["claim_id"], str)
    assert isinstance(result["policy_number"], str)
    assert isinstance(result["claim_type"], str)
    assert isinstance(result["status"], str)
    assert isinstance(result["amount"], (int, float))
