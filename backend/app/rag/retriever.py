from __future__ import annotations

"""
Chroma vector store retrieval module for OmniCare policy documents.

Best practices applied:
- Module-level singleton client and collection to avoid reloading the
  embedding model (SentenceTransformer) on every request (~200ms overhead).
- Distance thresholding to discard semantically irrelevant chunks before
  they can induce LLM hallucinations.
- Graceful empty-collection handling.
"""

import logging
from typing import Any

import chromadb
from chromadb.utils import embedding_functions

from app.config import settings

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
        embed_fn = embedding_functions.OpenAIEmbeddingFunction(
            api_key=settings.openai_api_key, model_name=embedding_model
        )
        _collection_cache[cache_key] = client.get_or_create_collection(
            name=collection_name,
            embedding_function=embed_fn,
        )

    return _collection_cache[cache_key]


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
    from reaching the LLM context window and causing hallucinations.

    Args:
        query: The natural-language search query.
        n_results: Maximum number of candidates to fetch before filtering.
        distance_threshold: Maximum L2 distance to consider relevant (default 1.3).
        chroma_path: Optional override for Chroma storage path.
        collection_name: Optional override for collection name.
        embedding_model: Optional override for embedding model name.

    Returns:
        List of dicts (sorted by distance, ascending) with keys:
            - document (str): Chunk text.
            - metadata (dict): Section, source, and chunk index fields.
            - distance (float): L2 distance from the query embedding.
    """
    collection = get_collection(chroma_path, collection_name, embedding_model)

    available = collection.count()
    if available == 0:
        logger.warning("Chroma collection is empty - RAG will return no results.")
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

    logger.debug("retrieve('%s'): %d/%d chunks passed threshold.", query, len(retrieved), n_fetch)
    return retrieved
