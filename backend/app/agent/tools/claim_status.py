from __future__ import annotations

"""
Claim status lookup tool for the OmniCare agent.
Reads from Postgres to find claim information securely linked to the current user.
"""

import logging
from typing import Any

from sqlalchemy import select

from app.agent.context import current_user_id
from app.database import async_session_factory
from app.models.claim import Claim

logger = logging.getLogger(__name__)


async def get_claim_status(claim_id: str, policy_number: str = "") -> dict[str, Any]:
    """Looks up the status of an existing OmniCare insurance claim by its ID.

    Use this tool when a user asks about the status, progress, or details of
    a specific claim. The claim ID is required. The policy number is optional.

    Args:
        claim_id (str): The unique claim identifier provided by the user.
            Example: "CLM-8821"
        policy_number (str, optional): The policyholder's policy number.

    Returns:
        dict: Claim status details.
    """
    try:
        user_uuid = current_user_id.get()
    except LookupError:
        logger.error("current_user_id not found in context.")
        return {"found": False, "error": "Unauthorized claim lookup."}

    normalised_id = claim_id.strip().upper()

    try:
        async with async_session_factory() as session:
            stmt = select(Claim).where(
                Claim.claim_id == normalised_id,
                Claim.owner_id == user_uuid
            )
            result = await session.execute(stmt)
            claim = result.scalar_one_or_none()

            if not claim:
                logger.warning(
                    "IDOR attempt or claim not found: claim %s requested by user %s",
                    normalised_id,
                    user_uuid,
                )
                return {
                    "found": False,
                    "error": (
                        f"No claim found with ID '{claim_id}'. "
                        "Please double-check the claim ID and try again, "
                        "or contact OmniCare support at 1-800-OMNICARE."
                    ),
                }

            logger.info("Claim '%s' found securely for owner '%s'.", normalised_id, user_uuid)
            return {
                "found": True,
                "claim_id": claim.claim_id,
                "policy_number": claim.policy_number,
                "claim_type": claim.claim_type,
                "status": claim.status,
                "amount": claim.amount,
                "citation": (
                    f"Claim {claim.claim_id} in the OmniCare claims system "
                    f"(policy {claim.policy_number})."
                ),
            }
    except Exception as exc:
        logger.exception("Database error during claim lookup: %s", exc)
        return {
            "found": False,
            "error": "Unable to retrieve claims at this time. Please contact support.",
        }
