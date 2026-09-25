from __future__ import annotations

"""
Hybrid retrieval module for OmniCare policy documents.

Retrieval strategy:
1. Primary: ChromaDB vector similarity search using OpenAI embeddings.
2. Fallback: Postgres BM25 full-text search via tsvector/tsquery when
   vector search returns no results above the distance threshold.

The BM25 fallback ensures exact keyword matches (deductibles, exclusions,
policy limits) are surfaced even when semantic similarity is weak.
"""

import logging
from typing import Any

import chromadb
from sqlalchemy import text

from app.config import settings
from app.database import async_session_factory

logger = logging.getLogger(__name__)

# Module-level singleton cache keyed by (chroma_path, collection_name, embedding_model).
# Loading the SentenceTransformer model from disk is expensive (~200 ms).
# We cache one (client, collection) pair so the model is initialised once per process.
_collection_cache: dict[tuple[str, str, str], Any] = {}


def get_collection(
    chroma_path: str | None = None,
    collection_name: str | None = None,
    embedding_model: str | None = None,
) -> Any:
    """
    Return a cached Chroma collection instance, creating it if necessary.

    Args:
        chroma_path: Filesystem path for Chroma persistence.
        collection_name: Name of the Chroma collection.
        embedding_model: Sentence-transformer model identifier.

    Returns:
        A Chroma Collection object ready for querying.
    """
    chroma_path = chroma_path or settings.chroma_db_path
    collection_name = collection_name or settings.chroma_collection_name
    embedding_model = embedding_model or settings.embedding_model

    cache_key = (chroma_path, collection_name, embedding_model)
    if cache_key not in _collection_cache:
        logger.debug(
            "Initialising Chroma collection '%s' at '%s' with model '%s'.",
            collection_name,
            chroma_path,
            embedding_model,
        )
        client = chromadb.PersistentClient(path=chroma_path)
        from app.rag.embedding import EmbeddingFactory

        embed_fn = EmbeddingFactory.get_embedding_function()
        _collection_cache[cache_key] = client.get_or_create_collection(
            name=collection_name,
            embedding_function=embed_fn,
        )

    return _collection_cache[cache_key]


async def _bm25_fallback(query: str, n_results: int = 5) -> list[dict[str, Any]]:
    """
    BM25 keyword search over Postgres policy_chunks tsvector column.

    Used as a fallback when vector search returns no results above the
    distance threshold. This catches exact keyword matches that semantic
    search might miss (e.g., specific deductible amounts, exclusion terms).

    Args:
        query: Natural-language search query.
        n_results: Maximum results to return.

    Returns:
        List of dicts with keys: document, metadata, distance (always 0.0
        since BM25 relevance is not a distance metric).
    """
    try:
        async with async_session_factory() as session:
            stmt = text("""
                SELECT text, section, source, chunk_index, sub_chunk_index,
                       ts_rank(tsvector, plainto_tsquery('english', :query)) AS rank
                FROM policy_chunks
                WHERE tsvector @@ plainto_tsquery('english', :query)
                ORDER BY rank DESC
                LIMIT :limit
            """)
            result = await session.execute(stmt, {"query": query, "limit": n_results})
            rows = result.mappings().all()

        retrieved: list[dict[str, Any]] = []
        for row in rows:
            retrieved.append(
                {
                    "document": row["text"],
                    "metadata": {
                        "section": row["section"],
                        "source": row["source"],
                        "chunk_index": row["chunk_index"],
                        "sub_chunk_index": row["sub_chunk_index"],
                    },
                    "distance": 0.0,
                    "_rank": float(row["rank"]),
                    "_source": "bm25",
                }
            )
        return retrieved
    except Exception as exc:
        logger.warning("BM25 fallback search failed: %s", exc)
        return []


def retrieve(  # noqa: PLR0913, PLR0917
    query: str,
    n_results: int = 5,
    distance_threshold: float = 1.3,
    chroma_path: str | None = None,
    collection_name: str | None = None,
    embedding_model: str | None = None,
) -> list[dict[str, Any]]:
    """
    Query the Chroma vector store for semantically relevant policy chunks.

    Results are filtered by a distance threshold to prevent irrelevant chunks
    from reaching the LLM context window and causing hallucinations. If no
    chunks pass the threshold, a BM25 keyword fallback over the Postgres
    tsvector index is attempted.

    Args:
        query: The natural-language search query.
        n_results: Maximum number of candidates to fetch before filtering.
        distance_threshold: Maximum L2 distance to consider relevant (default 1.3).
        chroma_path: Optional override for Chroma storage path.
        collection_name: Optional override for collection name.
        embedding_model: Optional override for embedding model name.

    Returns:
        List of dicts (sorted by relevance) with keys:
            - document (str): Chunk text.
            - metadata (dict): Section, source, and chunk index fields.
            - distance (float): L2 distance from the query embedding.
    """
    collection = get_collection(chroma_path, collection_name, embedding_model)

    available = collection.count()
    if available == 0:
        logger.warning("Chroma collection is empty - attempting BM25-only retrieval.")
        # Async fallback cannot be awaited here; return empty and let caller handle it
        return []

    n_fetch = min(n_results, available)

    raw = collection.query(
        query_texts=[query],
        n_results=n_fetch,
    )

    documents = raw.get("documents", [[]])[0]
    metadatas = raw.get("metadatas", [[]])[0]
    distances = raw.get("distances", [[]])[0]

    retrieved: list[dict[str, Any]] = []
    for doc, meta, dist in zip(documents, metadatas, distances, strict=True):
        if dist <= distance_threshold:
            retrieved.append({"document": doc, "metadata": meta, "distance": dist})
        else:
            logger.debug(
                "Discarding chunk (dist=%.4f > threshold=%.4f): '%s...'",
                dist,
                distance_threshold,
                doc[:60],
            )

    if not retrieved:
        logger.info("Vector search returned no results for '%s'. Falling back to BM25.", query)
        # Fire off BM25 fallback; the caller must await it if they want the result.
        # We return empty here and let the agent tool handle the async fallback.

    logger.debug("retrieve('%s'): %d/%d chunks passed threshold.", query, len(retrieved), n_fetch)
    return retrieved


async def retrieve_hybrid(
    query: str,
    n_results: int = 5,
    distance_threshold: float = 1.3,
    chroma_path: str | None = None,
    collection_name: str | None = None,
    embedding_model: str | None = None,
) -> list[dict[str, Any]]:
    """
    Hybrid retrieval: vector search first, BM25 fallback if vector search
    returns no results above the distance threshold.

    This is the preferred entry point for the agent tools. It handles the
    async BM25 fallback transparently.

    Args:
        query: The natural-language search query.
        n_results: Maximum number of candidates to fetch before filtering.
        distance_threshold: Maximum L2 distance to consider relevant.
        chroma_path: Optional override for Chroma storage path.
        collection_name: Optional override for collection name.
        embedding_model: Optional override for embedding model name.

    Returns:
        List of dicts (sorted by relevance) with keys:
            - document (str): Chunk text.
            - metadata (dict): Section, source, and chunk index fields.
            - distance (float): L2 distance or 0.0 for BM25 results.
    """
    # Primary: vector search
    results = retrieve(
        query=query,
        n_results=n_results,
        distance_threshold=distance_threshold,
        chroma_path=chroma_path,
        collection_name=collection_name,
        embedding_model=embedding_model,
    )

    if results:
        return results

    # Fallback: BM25 keyword search
    logger.info("Falling back to BM25 keyword search for query: %s", query)
    bm25_results = await _bm25_fallback(query, n_results=n_results)
    return bm25_results
