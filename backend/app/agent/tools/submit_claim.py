from __future__ import annotations

"""
Claim submission tool for the OmniCare agent.
Validates inputs with Pydantic and appends new claims to Postgres securely.
"""

import logging
import uuid
from typing import Any

from pydantic import ValidationError

from app.agent.context import current_user_id
from app.database import async_session_factory
from app.models.claim import Claim
from app.schemas.models import ClaimSubmission

logger = logging.getLogger(__name__)


async def submit_claim(
    policy_number: str,
    claim_type: str,
    amount: float,
    description: str,
) -> dict[str, Any]:
    """Submits a new OmniCare insurance claim on behalf of the policyholder.

    Use this tool when the user explicitly wants to file a new claim. Collect
    all four required fields before calling. If any field is ambiguous, confirm
    with the user before submitting.

    Args:
        policy_number (str): The policyholder's policy number (e.g., "POL-1092").
        claim_type (str): Category of the claim (e.g., "Water Damage", "Personal Property").
        amount (float): Claimed amount in US dollars. Must be greater than 0.
        description (str): Factual description of the incident (minimum 10 characters).

    Returns:
        dict: Submission confirmation or error.
    """
    try:
        user_uuid = current_user_id.get()
    except LookupError:
        logger.error("current_user_id not found in context.")
        return {"success": False, "error": "Unauthorized submission."}

    try:
        validated = ClaimSubmission(
            policy_number=policy_number,
            claim_type=claim_type,
            amount=amount,
            description=description,
        )
    except ValidationError as exc:
        errors = [f"{err['loc'][-1] if err['loc'] else 'field'}: {err['msg']}" for err in exc.errors()]
        logger.warning("Claim submission validation failed: %s", errors)
        return {"success": False, "validation_errors": errors}

    confirmation_id = f"CLM-{uuid.uuid4().hex[:4].upper()}"

    try:
        async with async_session_factory() as session:
            new_claim = Claim(
                claim_id=confirmation_id,
                policy_number=validated.policy_number,
                claim_type=validated.claim_type,
                status="Submitted",
                amount=validated.amount,
                description=validated.description,
                owner_id=user_uuid,
            )
            session.add(new_claim)
            await session.commit()
    except Exception as exc:
        logger.exception("Failed to persist claim '%s': %s", confirmation_id, exc)
        return {
            "success": False,
            "error": "Your claim could not be saved. Please try again or contact support.",
        }

    logger.info("Claim '%s' submitted for policy '%s'.", confirmation_id, validated.policy_number)

    return {
        "success": True,
        "confirmation_id": confirmation_id,
        "status": "Submitted",
        "policy_number": validated.policy_number,
        "claim_type": validated.claim_type,
        "amount": validated.amount,
        "description": validated.description,
        "message": (
            f"Your claim {confirmation_id} has been successfully submitted "
            "and is now being processed. Keep this ID for your records."
        ),
    }
