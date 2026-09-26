"""
Claims RAG module for the OmniCare backend.

Provides hybrid search over user claims using the configured vector store.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.database import async_session_factory
from app.rag.vector_store import get_vector_store
from app.rag.embedding import EmbeddingFactory

logger = logging.getLogger(__name__)


async def retrieve_claims_hybrid(
    query: str,
    user_id: uuid.UUID,
    n_results: int = 5,
    distance_threshold: float = 1.3,
) -> list[dict[str, Any]]:
    """Hybrid search for claims belonging to a specific user.

    Combines vector similarity search with BM25 keyword search using RRF.

    Args:
        query: Natural language search query.
        user_id: UUID of the claim owner.
        n_results: Maximum number of results.
        distance_threshold: Maximum L2 distance for vector search.

    Returns:
        List of result dicts with document, metadata, distance, _rrf_score.
    """
    try:
        store = get_vector_store(table_name="claims", id_field="id")
        embed_fn = EmbeddingFactory.get_embedding_function()
        query_embedding = embed_fn([query])[0]

        return await store.hybrid_search(
            query=query,
            embedding=query_embedding,
            n_results=n_results,
            threshold=distance_threshold,
            text_field="description",
            metadata_fields=["claim_id", "policy_number", "claim_type", "status", "amount"],
            owner_id=str(user_id),
        )
    except Exception as exc:
        logger.error("Hybrid claims search failed: %s", exc)
        return []


async def ingest_claim(  # noqa: PLR0913, PLR0917
    claim_id: str,
    owner_id: uuid.UUID,
    claim_type: str,
    description: str,
    policy_number: str,
    status: str,
    amount: float,
):
    """Ingest a single claim into the vector store.

    Args:
        claim_id: Unique claim identifier.
        owner_id: UUID of the claim owner.
        claim_type: Type of claim.
        description: Claim description text.
        policy_number: Associated policy number.
        status: Current claim status.
        amount: Claim amount.
    """
    embed_fn = EmbeddingFactory.get_embedding_function()
    text_content = f"Claim {claim_id}: {claim_type} - {description}"
    embedding = embed_fn([text_content])[0]

    store = get_vector_store(table_name="claims", id_field="id")
    await store.upsert(
        documents=[
            {
                "id": claim_id,
                "text": text_content,
                "embedding": embedding,
                "claim_id": claim_id,
                "policy_number": policy_number,
                "claim_type": claim_type,
                "status": status,
                "amount": amount,
                "description": description,
                "owner_id": str(owner_id),
            }
        ],
    )


async def ingest_all_claims():
    """Ingest all claims from the database into the vector store."""
    from sqlalchemy import select  # noqa: PLC0415
    from app.models.claim import Claim  # noqa: PLC0415

    async with async_session_factory() as session:
        result = await session.execute(select(Claim))
        claims = result.scalars().all()

    for claim in claims:
        await ingest_claim(
            claim_id=claim.claim_id,
            owner_id=claim.owner_id,
            claim_type=claim.claim_type,
            description=claim.description,
            policy_number=claim.policy_number,
            status=claim.status,
            amount=claim.amount,
        )
