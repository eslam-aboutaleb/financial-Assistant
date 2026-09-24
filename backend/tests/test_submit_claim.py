"""
Direct unit tests for the submit_claim tool function.

Tests:
- test_submit_valid_claim: Submit with valid data, verify returns confirmation_id starting with 'CLM-'
- test_submit_claim_appends_to_file: Submit a claim, read the JSON file, verify new claim exists
- test_submit_invalid_negative_amount: Amount < 0 should return validation error
- test_submit_short_description: Description < 10 chars should return validation error
- test_submit_generates_unique_ids: Submit two claims, verify different confirmation IDs
"""

import json

from app.agent.tools.submit_claim import submit_claim


def test_submit_valid_claim(sample_claims_path):
    """
    Test submitting a valid claim.
    Verifies that confirmation_id begins with 'CLM-', status is 'Submitted',
    and all fields are returned in the response.
    Verifies that success=True, confirmation_id begins with 'CLM-',
    status is 'Submitted', and all fields are echoed back in the response.
    """
    result = submit_claim(
        policy_number="POL-1092",
        claim_type="Water Damage",
        amount=2500.00,
        description="Frozen pipe burst causing water damage to hardwood floors",
    )

    assert "error" not in result, f"Unexpected error returned: {result}"
    assert result.get("success") is True, f"Expected success=True, got: {result}"
    assert "confirmation_id" in result, f"Missing 'confirmation_id' in response: {result}"
    assert result["confirmation_id"].startswith("CLM-"), (
        f"Expected confirmation_id to start with 'CLM-', got: {result['confirmation_id']}"
    )
    assert result["status"] == "Submitted"
    assert result["policy_number"] == "POL-1092"
    assert result["claim_type"] == "Water Damage"
    assert result["amount"] == 2500.00
    assert result["description"] == "Frozen pipe burst causing water damage to hardwood floors"


def test_submit_claim_appends_to_file(sample_claims_path):
    """
    Test that submitting a claim persists the record to the JSON file.
    Reads sample_claims_path before and after submission to verify the
    claim count increases and the new record is present with correct data.
    """
    initial_content = json.loads(sample_claims_path.read_text(encoding="utf-8"))
    initial_count = len(initial_content)

    result = submit_claim(
        policy_number="POL-4455",
        claim_type="Personal Property",
        amount=850.50,
        description="Laptop stolen from locked apartment during burglary",
    )

    assert "confirmation_id" in result
    new_claim_id = result["confirmation_id"]

    # Re-read file and assert claim has been persisted
    updated_content = json.loads(sample_claims_path.read_text(encoding="utf-8"))
    assert len(updated_content) == initial_count + 1, (
        f"Expected claims count to increase from {initial_count} to {initial_count + 1}"
    )

    matching_claims = [c for c in updated_content if c.get("claim_id") == new_claim_id]
    assert len(matching_claims) == 1, f"Claim {new_claim_id} not found in claims file"

    persisted = matching_claims[0]
    assert persisted["policy_number"] == "POL-4455"
    assert persisted["claim_type"] == "Personal Property"
    assert persisted["status"] == "Submitted"
    assert persisted["amount"] == 850.50
    assert persisted["description"] == "Laptop stolen from locked apartment during burglary"


def test_submit_invalid_negative_amount(sample_claims_path):
    """
    Test that amount < 0 returns a validation error and does not persist any claim.
    """
    initial_content = json.loads(sample_claims_path.read_text(encoding="utf-8"))

    result = submit_claim(
        policy_number="POL-1092",
        claim_type="Water Damage",
        amount=-500.00,
        description="Negative claim amount should fail validation",
    )

    assert result.get("success") is False, (
        f"Expected success=False for negative amount, got: {result}"
    )
    assert "validation_errors" in result, (
        f"Expected 'validation_errors' key in response, got: {result}"
    )

    # Check error details mention the amount field
    errors_str = json.dumps(result.get("validation_errors", []))
    assert "amount" in errors_str.lower(), (
        f"'amount' not referenced in validation_errors: {errors_str}"
    )

    # File should not have changed
    current_content = json.loads(sample_claims_path.read_text(encoding="utf-8"))
    assert len(current_content) == len(initial_content)


def test_submit_short_description(sample_claims_path):
    """
    Test that description < 10 characters returns a validation error.
    """
    initial_content = json.loads(sample_claims_path.read_text(encoding="utf-8"))

    result = submit_claim(
        policy_number="POL-1092",
        claim_type="Water Damage",
        amount=150.00,
        description="Too short",  # 9 characters (< 10)
    )

    assert result.get("success") is False, (
        f"Expected success=False for short description, got: {result}"
    )
    assert "validation_errors" in result, (
        f"Expected 'validation_errors' key in response, got: {result}"
    )

    # Check error details mention the description field
    errors_str = json.dumps(result.get("validation_errors", []))
    assert "description" in errors_str.lower(), (
        f"'description' not referenced in validation_errors: {errors_str}"
    )

    # File should not have changed
    current_content = json.loads(sample_claims_path.read_text(encoding="utf-8"))
    assert len(current_content) == len(initial_content)


def test_submit_generates_unique_ids(sample_claims_path):
    """
    Test that submitting two claims generates distinct confirmation IDs.
    """
    res1 = submit_claim(
        policy_number="POL-1092",
        claim_type="Water Damage",
        amount=1200.00,
        description="First claim for water leak repair in bathroom",
    )
    res2 = submit_claim(
        policy_number="POL-3341",
        claim_type="Personal Property",
        amount=950.00,
        description="Second claim for broken television screen",
    )

    assert "confirmation_id" in res1
    assert "confirmation_id" in res2
    assert res1["confirmation_id"].startswith("CLM-")
    assert res2["confirmation_id"].startswith("CLM-")

    assert res1["confirmation_id"] != res2["confirmation_id"], (
        f"Expected distinct confirmation IDs, but got {res1['confirmation_id']} twice"
    )
