"""
Vector store abstraction for the OmniCare RAG subsystem.

Defines the interface for hybrid retrieval (vector + BM25) operations,
allowing different backends (pgvector, ChromaDB, etc.) to be swapped
via configuration without changing the retriever or ingestion code.
"""

from abc import ABC, abstractmethod
from typing import Any

from app.config import get_settings
from app.rag.pgvector_store import PgVectorStore


class VectorStore(ABC):
    """Abstract interface for vector store operations."""

    @abstractmethod
    async def hybrid_search(
        self,
        query: str,
        embedding: list[float],
        n_results: int,
        threshold: float,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        """Perform hybrid vector + BM25 search using Reciprocal Rank Fusion.

        Args:
            query: Natural language search query.
            embedding: Query embedding vector.
            n_results: Maximum number of results to return.
            threshold: Maximum distance for vector search part.
            **filters: Additional filters (e.g., owner_id for claims).

        Returns:
            List of result dicts with keys: document, metadata, distance, _rrf_score.
        """
        ...

    @abstractmethod
    async def count(self, **filters: Any) -> int:
        """Count documents in the store.

        Args:
            **filters: Optional filters (e.g., owner_id for claims).

        Returns:
            Number of matching documents.
        """
        ...

    @abstractmethod
    async def upsert(self, documents: list[dict[str, Any]], **filters: Any) -> None:
        """Upsert documents into the store.

        Args:
            documents: List of document dicts with keys: id, text, metadata, embedding.
            **filters: Additional fields (e.g., owner_id for claims).
        """
        ...


def get_vector_store(
    table_name: str,
    id_field: str = "id",
    embedding_dim: int = 1536,
) -> VectorStore:
    """Factory function to create a vector store instance.

    Args:
        table_name: Name of the database table.
        id_field: Name of the ID column.
        embedding_dim: Dimension of the embedding vectors.

    Returns:
        Configured VectorStore instance based on provider setting.
    """
    settings = get_settings()
    provider = getattr(settings, "vector_store_provider", "pgvector")

    if provider == "pgvector":
        return PgVectorStore(table_name=table_name, id_field=id_field, embedding_dim=embedding_dim)
    raise ValueError(f"Unsupported vector store provider: {provider}")
