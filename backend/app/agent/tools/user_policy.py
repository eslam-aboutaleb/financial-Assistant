from __future__ import annotations

"""
User policy lookup tool for the OmniCare agent.
Reads active policies for the current authenticated user.
"""

import logging
from typing import Any

from sqlalchemy import select

from app.agent.context import current_user_id
from app.database import async_session_factory
from app.models.claim import Claim

logger = logging.getLogger(__name__)

async def get_user_policies() -> dict[str, Any]:
    """Retrieves the list of active insurance policies held by the current user.

    Use this tool when the user asks questions like 'What is my policy?', 
    'What policies do I have?', or 'What is my policy number?'.

    Returns:
        dict: A list of the user's active policies and their coverage details.
    """
    try:
        user_uuid = current_user_id.get()
    except LookupError:
        logger.error("current_user_id not found in context.")
        return {"success": False, "error": "Unauthorized policy lookup."}

    try:
        async with async_session_factory() as session:
            # Query the user's distinct policy numbers from their claims history.
            stmt = select(Claim.policy_number).where(Claim.owner_id == user_uuid).distinct()
            result = await session.execute(stmt)
            policy_numbers = [row[0] for row in result.all()]
            
            # For the scope of this PDF prototype, if they don't have claims yet, 
            # we simulate an active policy assignment to respect the flow.
            if not policy_numbers:
                policy_numbers = ["POL-1092"] # Mock policy from the PDF
            
            return {
                "success": True,
                "policies": [
                    {
                        "policy_number": pn,
                        "type": "OmniCare General Insurance (Home Water Damage & Personal Property)",
                        "status": "Active"
                    }
                    for pn in policy_numbers
                ],
                "message": "These are the active policies for the user. Remind the user that these policies cover Home Water Damage and Personal Property, as per OmniCare General Insurance rules."
            }
    except Exception as exc:
        logger.exception("Database error during policy lookup: %s", exc)
        return {
            "success": False,
            "error": "Unable to retrieve policy details at this time. Please contact support.",
        }
