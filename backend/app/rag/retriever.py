"""
Hybrid retrieval module for OmniCare policy documents.

Uses the configured VectorStore (pgvector by default) for hybrid search
combining vector similarity with BM25 full-text search.
"""

from __future__ import annotations

import logging
from typing import Any

from app.rag.embedding import EmbeddingFactory
from app.rag.vector_store import get_vector_store

logger = logging.getLogger(__name__)


async def retrieve_hybrid(
    query: str,
    n_results: int = 5,
    distance_threshold: float = 1.3,
) -> list[dict[str, Any]]:
    """Hybrid retrieval: vector search + BM25 keyword search using RRF.

    Args:
        query: The natural-language search query.
        n_results: Maximum number of candidates to fetch.
        distance_threshold: Maximum L2 distance for the vector search part.

    Returns:
        List of dicts (sorted by RRF score) with keys:
            - document (str): Chunk text.
            - metadata (dict): Section, source, and chunk index fields.
            - distance (float): The L2 distance (if found by vector search).
    """
    try:
        store = get_vector_store(table_name="policy_chunks", id_field="id")
        embed_fn = EmbeddingFactory.get_embedding_function()
        query_embedding = embed_fn([query])[0]

        return await store.hybrid_search(
            query=query,
            embedding=query_embedding,
            n_results=n_results,
            threshold=distance_threshold,
            text_field="text",
            metadata_fields=["section", "source", "chunk_index", "sub_chunk_index"],
        )
    except Exception as exc:
        logger.error("Hybrid retrieval failed: %s", exc)
        return []
