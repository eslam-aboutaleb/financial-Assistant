"""
Agent tools package for the OmniCare Financial backend.

Contains all tool functions registered with the Google ADK LlmAgent.
Each tool is a standalone async function that the agent can invoke
based on user intent:

  - ``query_policy``    -- RAG search over pgvector policy documents.
  - ``get_claim_status`` -- Owner-scoped Postgres claim lookup.
  - ``submit_claim``    -- Pydantic-validated claim insertion.
"""

from app.agent.tools.policy_rag import query_policy
from app.agent.tools.claim_status import get_claim_status
from app.agent.tools.submit_claim import submit_claim

__all__ = ["query_policy", "get_claim_status", "submit_claim"]
