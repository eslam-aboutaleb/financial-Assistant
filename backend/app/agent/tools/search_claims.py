"""
Natural-language search tool for the OmniCare AI agent.

This module exposes the ``search_claims`` tool that the agent invokes when a
user asks about their claims history without providing a specific claim ID
(e.g., "Have I ever filed a claim for water damage?").

Retrieval strategy:
  - Primary: Hybrid vector search via ChromaDB. Claims are embedded at
    ingestion time using the configured OpenAI embedding model. The hybrid
    approach combines semantic similarity with keyword matching for robustness.
  - Fallback: BM25 full-text search over the Postgres ``claims`` table when
    the vector collection is empty or returns no results above the distance
    threshold.

Security:
  - The tool always scopes results to the authenticated user's ``owner_id``.
    Even if the underlying collection had no access controls, the BM25
    fallback filters by ``owner_id`` to prevent cross-user data leakage.
"""

import logging
from typing import Any

from app.agent.context import current_user_id
from app.rag.claims_rag import retrieve_claims_hybrid

logger = logging.getLogger(__name__)


async def search_claims(query: str, n_results: int = 5) -> list[dict[str, Any]]:
    """Search the authenticated user's claims using natural language.

    This tool is intended (filters by owner_id) for open-ended claims history questions. For
    lookups of a specific claim by ID, the ``get_claim_status`` tool is
    more appropriate.

    Args:
        query: Natural language search query (e.g., "water damage in kitchen").
        n_results: Maximum number of claims to return. Defaults to 5.

    Returns:
        list[dict]: A list of matching claims. Each dict contains at least
        ``document`` (the rendered claim text), ``metadata`` (structured claim
        fields), and ``distance`` (vector similarity score). On error, returns
        a list with a single ``error`` key.
    """
    try:
        user_uuid = current_user_id.get()
    except LookupError:
        # This should never happen in production because the endpoint
        # dependency sets current_user_id before agent execution. It is
        # caught here as a defense-in-depth measure.
        logger.error("current_user_id not found in context during claims search.")
        return [{"error": "Unauthorized claim search."}]

    try:
        results = await retrieve_claims_hybrid(query=query, user_id=user_uuid, n_results=n_results)

        if not results:
            return [{"message": "No relevant claims found matching your search."}]

        return results
    except Exception as exc:
        logger.exception("Error during hybrid claims search: %s", exc)
        return [{"error": "Unable to search claims at this time. Please try again later."}]
