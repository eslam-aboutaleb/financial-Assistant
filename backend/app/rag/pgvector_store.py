"""
pgvector implementation of the VectorStore interface.

Provides hybrid search (vector + BM25 RRF), document counting, and upsert
operations against PostgreSQL tables with pgvector and tsvector columns.

Security model:
  - All user-supplied **values** are passed as bound parameters via SQLAlchemy's
    parameterized queries. They never appear in the SQL string, so they cannot
    inject SQL.
  - All **SQL identifiers** (table names, column names, filter keys) are
    validated against a strict allowlist regex (``^[A-Za-z_][A-Za-z0-9_]*$``)
    before interpolation into raw SQL strings. This prevents SQL injection even
    when identifiers are derived from configuration.
  - Raw SQL is used because the hybrid search query requires complex CTEs with
    window functions, pgvector operators, and BM25 full-text search that are
    impractical to express in SQLAlchemy ORM/Core while remaining readable.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from app.config import get_settings
from app.database import async_session_factory
from app.rag.embedding import EmbeddingFactory

logger = logging.getLogger(__name__)


def _validate_identifier(name: str, label: str) -> None:
    """Validate that a string is a safe SQL identifier (table, column, etc.).

    Only allows alphanumeric characters and underscores, starting with a
    letter or underscore. This is a strict whitelist that prevents SQL
    injection through identifier interpolation.

    Args:
        name: The identifier string to validate.
        label: Human-readable label for error messages.

    Raises:
        ValueError: If the identifier contains unsafe characters.
    """
    import re  # noqa: PLC0415

    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
        raise ValueError(f"Unsafe {label}: {name!r}")


class PgVectorStore:
    """pgvector-based vector store implementation.

    Supports hybrid search combining vector similarity (pgvector <-> operator)
    with BM25 full-text search (tsvector/tsquery) using Reciprocal Rank Fusion.
    """

    def __init__(self, table_name: str, id_field: str = "id", embedding_dim: int = 1536):
        """Initialize the vector store with target table configuration.

        Args:
            table_name: Name of the database table containing vector data.
            id_field: Name of the primary key column. Defaults to "id".
            embedding_dim: Dimensionality of the embedding vectors. Defaults to 1536.

        Raises:
            ValueError: If ``table_name`` or ``id_field`` contain unsafe characters.
        """
        _validate_identifier(table_name, "table_name")
        _validate_identifier(id_field, "id_field")
        self.table_name = table_name
        self.id_field = id_field
        self.embedding_dim = embedding_dim
        self._settings = get_settings()

    async def hybrid_search(  # noqa: PLR0913, PLR0917
        self,
        query: str,
        embedding: list[float],
        n_results: int,
        threshold: float,
        text_field: str = "text",
        metadata_fields: list[str] | None = None,
        **filters: Any,
    ) -> list[dict[str, Any]]:
        """Hybrid search with vector + BM25 RRF.

        Executes a two-stage retrieval:
          1. Vector search using pgvector L2 distance with a distance threshold.
          2. BM25 keyword search using PostgreSQL full-text search.

        Results from both stages are merged using Reciprocal Rank Fusion (RRF),
        which combines the ranks from each retrieval method to produce a unified
        ranking. This approach is robust when one retrieval method fails to
        find relevant documents.

        Args:
            query: Natural language search query.
            embedding: Query embedding vector. If empty, the query is embedded
                automatically using the configured embedding function.
            n_results: Maximum number of results to return.
            threshold: Maximum L2 distance for the vector search part. Smaller
                values enforce stricter similarity matching.
            text_field: Name of the column containing the document text.
            metadata_fields: List of additional column names to include in the
                result metadata dict.
            **filters: Additional equality filters applied to both search CTEs
                (e.g., ``owner_id="..."``). Keys must be valid SQL identifiers;
                values are bound as parameters to prevent SQL injection.

        Returns:
            list[dict]: A list of result dicts sorted by RRF score, each
            containing:
                - ``document`` (str): The retrieved text.
                - ``metadata`` (dict): Structured metadata fields.
                - ``distance`` (float): L2 distance from the vector search.
                - ``_rrf_score`` (float): Combined RRF relevance score.
        """
        _validate_identifier(text_field, "text_field")
        for key in filters:
            _validate_identifier(key, "filter key")
        metadata_fields = metadata_fields or []
        for field in metadata_fields:
            _validate_identifier(field, "metadata_field")

        embed_fn = EmbeddingFactory.get_embedding_function()
        if not embedding:
            embedding = embed_fn([query])[0]

        embedding_str = f"[{','.join(str(x) for x in embedding)}]"
        metadata_fields = metadata_fields or []

        # Build SELECT clause for metadata fields so they are returned in
        # both the vector and keyword CTEs.
        meta_select = ", ".join(metadata_fields) if metadata_fields else ""
        if metadata_fields:
            meta_coalesce = ", ".join(f"v.{f}, k.{f}" for f in metadata_fields)
        else:
            meta_coalesce = ""

        # Build JOIN condition between the two CTEs.
        join_conditions = [f"v.{self.id_field} = k.{self.id_field}"]

        # Build query parameters and WHERE fragments from validated filters.
        params: dict[str, Any] = {
            "query": query,
            "embedding": embedding_str,
            "distance_threshold": threshold,
            "n_results": n_results,
        }
        filter_parts: list[str] = []
        for key, value in filters.items():
            filter_parts.append(f"{key} = :{key}")
            params[key] = value

        extra_where = " AND ".join(filter_parts) if filter_parts else None
        if extra_where:
            join_conditions.append(extra_where)

        join_sql = " AND ".join(join_conditions)

        stmt = text(
            f"""
            WITH vector_search AS (
                SELECT {self.id_field}, {text_field}, {meta_select},
                       embedding <-> cast(:embedding as vector) AS distance,
                       ROW_NUMBER() OVER (ORDER BY embedding <-> cast(:embedding as vector)) AS rank
                FROM {self.table_name}
                WHERE embedding <-> cast(:embedding as vector) < :distance_threshold
                {f"AND {extra_where}" if extra_where else ""}
                LIMIT :n_results
            ),
            keyword_search AS (
                SELECT {self.id_field}, {text_field}, {meta_select},
                       ts_rank(tsvector, plainto_tsquery('english', :query)) AS score,
                       ROW_NUMBER() OVER (
                           ORDER BY ts_rank(tsvector, plainto_tsquery('english', :query)) DESC
                       ) AS rank
                FROM {self.table_name}
                WHERE tsvector @@ plainto_tsquery('english', :query)
                {f"AND {extra_where}" if extra_where else ""}
                LIMIT :n_results
            )
            SELECT
                COALESCE(v.{self.id_field}, k.{self.id_field}) AS id,
                COALESCE(v.{text_field}, k.{text_field}) AS document,
                {meta_coalesce},
                v.distance AS distance,
                k.score AS keyword_score,
                COALESCE(1.0 / (60 + v.rank), 0.0) + COALESCE(1.0 / (60 + k.rank), 0.0) AS rrf_score
            FROM vector_search v
            FULL OUTER JOIN keyword_search k ON {join_sql}
            ORDER BY rrf_score DESC
            LIMIT :n_results
        """
        )

        try:
            async with async_session_factory() as session:
                result = await session.execute(stmt, params)
                rows = result.mappings().all()

            retrieved = []
            for row in rows:
                metadata = {}
                for field in metadata_fields:
                    if field in row and row[field] is not None:
                        metadata[field] = row[field]

                retrieved.append(
                    {
                        "document": row["document"],
                        "metadata": metadata,
                        "distance": float(row["distance"]) if row["distance"] is not None else 0.0,
                        "_rrf_score": float(row["rrf_score"]),
                    }
                )

            logger.debug(
                "hybrid_search('%s') on %s: found %d results.",
                query,
                self.table_name,
                len(retrieved),
            )
            return retrieved
        except Exception as exc:
            logger.error("Hybrid search failed on %s: %s", self.table_name, exc)
            return []

    async def count(self, **filters: Any) -> int:
        """Count documents in the store.

        Args:
            **filters: Optional equality filters (e.g., ``owner_id="..."``).
                Keys must be valid SQL identifiers; values are bound as
                parameters to prevent SQL injection.

        Returns:
            int: Number of matching documents, or 0 on error.
        """
        for key in filters:
            _validate_identifier(key, "filter key")

        params: dict[str, Any] = {}
        filter_parts: list[str] = []
        for key, value in filters.items():
            filter_parts.append(f"{key} = :{key}")
            params[key] = value

        where_clause = f"WHERE {' AND '.join(filter_parts)}" if filter_parts else ""

        stmt = text(
            f"""
            SELECT COUNT(*) FROM {self.table_name}
            {where_clause}
        """
        )

        try:
            async with async_session_factory() as session:
                result = await session.execute(stmt, params)
                count = result.scalar_one()
            return int(count) if count else 0
        except Exception as exc:
            logger.error("Count failed on %s: %s", self.table_name, exc)
            return 0

    async def upsert(
        self,
        documents: list[dict[str, Any]],
        text_field: str = "text",
        embedding_field: str = "embedding",
        id_field: str = "id",
        extra_fields: dict[str, Any] | None = None,
    ) -> None:
        """Upsert documents into the store.

        Inserts or updates documents using PostgreSQL's ``ON CONFLICT ... DO UPDATE``
        syntax. This allows the ingestion pipeline to re-run without creating
        duplicate rows.

        Args:
            documents: List of document dicts with keys: id, text, metadata,
                embedding. Metadata keys are included as additional columns.
            text_field: Name of the text column. Defaults to "text".
            embedding_field: Name of the embedding column. Defaults to "embedding".
            id_field: Name of the primary key column. Defaults to "id".
            extra_fields: Additional static fields to include in every INSERT
                (e.g., ``{"owner_id": "..."}``).

        Raises:
            ValueError: If any column name contains unsafe characters.
            Exception: Re-raises database errors after logging.
        """
        _validate_identifier(text_field, "text_field")
        _validate_identifier(embedding_field, "embedding_field")
        _validate_identifier(id_field, "id_field")
        if extra_fields:
            for key in extra_fields:
                _validate_identifier(key, "extra_field")

        if not documents:
            return

        try:
            async with async_session_factory() as session:
                for doc in documents:
                    # Build column names and parameter placeholders for the
                    # INSERT statement. Columns include: id, text, embedding,
                    # plus any metadata keys and extra_fields.
                    columns = [id_field, text_field, embedding_field]
                    placeholders = [f":{id_field}", f":{text_field}", f":{embedding_field}"]

                    params: dict[str, Any] = {
                        id_field: doc.get("id"),
                        text_field: doc["text"],
                        # Embeddings are stored as PostgreSQL vector literals
                        # (e.g., "[0.1,0.2,...]") for direct insertion.
                        embedding_field: f"[{','.join(str(x) for x in doc['embedding'])}]",
                    }

                    # Add metadata fields from the document dict.
                    for key, value in doc.get("metadata", {}).items():
                        columns.append(key)
                        placeholders.append(f":{key}")
                        params[key] = value

                    # Add static extra fields (same value for all documents).
                    if extra_fields:
                        for key, value in extra_fields.items():
                            columns.append(key)
                            placeholders.append(f":{key}")
                            params[key] = value

                    columns_str = ", ".join(columns)
                    placeholders_str = ", ".join(placeholders)

                    # Build ON CONFLICT clause: update all non-ID columns.
                    update_cols = [c for c in columns if c != id_field]
                    update_str = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)

                    stmt = text(
                        f"""
                        INSERT INTO {self.table_name} ({columns_str})
                        VALUES ({placeholders_str})
                        ON CONFLICT ({id_field}) DO UPDATE SET {update_str}
                    """
                    )

                    await session.execute(stmt, params)

                await session.commit()
            logger.info("Upserted %d documents to %s.", len(documents), self.table_name)
        except Exception as exc:
            logger.error("Upsert failed on %s: %s", self.table_name, exc)
            raise
