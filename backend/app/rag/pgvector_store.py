"""
pgvector implementation of the VectorStore interface.

Provides hybrid search (vector + PostgreSQL full-text search RRF), document counting, and upsert
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
    window functions, pgvector operators, and PostgreSQL full-text search that are
    impractical to express in SQLAlchemy ORM/Core while remaining readable.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from sqlalchemy import text

from app.rag.embedding_dimensions import get_embedding_dimension
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

    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError(f"Unsafe {label}: {name!r}")


def _keyword_score(row: Any) -> float | None:
    """Return the PostgreSQL full-text rank from a hybrid search row, if present.

    The column is absent for a vector-only hit, and the projection is not guaranteed
    across every caller, so membership is checked rather than assumed.
    """
    if "keyword_score" not in row:
        return None
    value = row["keyword_score"]
    return None if value is None else float(value)


def _validate_embedding(
    embedding: list[float],
    expected_dim: int,
    label: str = "embedding",
) -> None:
    """Validate that an embedding vector has the expected dimension and contains only finite values.

    Args:
        embedding: The embedding vector to validate.
        expected_dim: Expected dimensionality of the embedding.
        label: Human-readable label for error messages.

    Raises:
        ValueError: If the embedding has the wrong dimension or contains non-finite values.
        TypeError: If a value in the embedding is not a number.
    """
    if len(embedding) != expected_dim:
        raise ValueError(f"{label} has {len(embedding)} dimensions; expected {expected_dim}")
    for i, value in enumerate(embedding):
        try:
            if not math.isfinite(value):
                raise ValueError(f"{label}[{i}] is not finite: {value!r}")
        except TypeError as exc:
            raise TypeError(f"{label}[{i}] is not a number: {value!r}") from exc


class PgVectorStore:
    """pgvector-based vector store implementation.

    Supports hybrid search combining vector similarity (pgvector <-> operator)
    with PostgreSQL full-text search (tsvector/tsquery) using Reciprocal Rank Fusion.
    """

    def __init__(self, table_name: str, id_field: str = "id", embedding_dim: int | None = None):
        """Initialize the vector store with target table configuration.

        Args:
            table_name: Name of the database table containing vector data.
            id_field: Name of the primary key column. Defaults to "id".
            embedding_dim: Dimensionality of the embedding vectors. Defaults to the
                dimension configured for the active embedding model.

        Raises:
            ValueError: If ``table_name`` or ``id_field`` contain unsafe characters.
        """
        _validate_identifier(table_name, "table_name")
        _validate_identifier(id_field, "id_field")
        self.table_name = table_name
        self.id_field = id_field
        self.embedding_dim = (
            embedding_dim if embedding_dim is not None else get_embedding_dimension()
        )
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
        """Hybrid search with vector + PostgreSQL full-text search RRF.

        Executes a two-stage retrieval:
          1. Vector search using pgvector L2 distance with a distance threshold.
          2. PostgreSQL full-text search using tsvector/tsquery.

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
            embedding_list = await embed_fn([query])
            embedding = embedding_list[0]

        _validate_embedding(embedding, self.embedding_dim, label="query embedding")
        metadata_fields = metadata_fields or []

        # Build SELECT clause for metadata fields so they are returned in
        # both the vector and keyword CTEs. This ensures metadata is available
        # regardless of which search method found the document.
        vector_select = [
            self.id_field,
            text_field,
        ]
        vector_select.extend(metadata_fields)
        vector_select_sql = ", ".join(vector_select)

        keyword_select = [
            self.id_field,
            text_field,
        ]
        keyword_select.extend(metadata_fields)
        keyword_select_sql = ", ".join(keyword_select)

        if metadata_fields:
            # Each COALESCE column is aliased with its field name.
            # Without the alias PostgreSQL labels every one of them
            # "coalesce", so the result mapping never contains the
            # field names and every result would carry empty metadata.
            meta_coalesce = ", ".join(f"COALESCE(v.{f}, k.{f}) AS {f}" for f in metadata_fields)
        else:
            meta_coalesce = ""

        # The outer projection is assembled as a list so that an empty
        # ``metadata_fields`` contributes no element. Interpolating the metadata
        # expression as ``f"{meta_coalesce},"`` emits a bare comma when it is empty,
        # producing ``AS document, , v.distance`` — a syntax error that is then
        # swallowed by the broad ``except`` below and reported as "no results".
        outer_select = [
            f"COALESCE(v.{self.id_field}, k.{self.id_field}) AS id",
            f"COALESCE(v.{text_field}, k.{text_field}) AS document",
        ]
        if metadata_fields:
            outer_select.append(meta_coalesce)
        outer_select.extend(
            [
                "v.distance AS distance",
                "k.score AS keyword_score",
                (
                    "COALESCE(1.0 / (60 + v.rank), 0.0) "
                    "+ COALESCE(1.0 / (60 + k.rank), 0.0) AS rrf_score"
                ),
            ]
        )
        outer_select_sql = ",\n                 ".join(outer_select)

        # Build JOIN condition between the two CTEs. The primary join is on
        # the document ID field, with optional additional filters applied
        # to both sides to ensure consistent scoping.
        join_conditions = [f"v.{self.id_field} = k.{self.id_field}"]

        # Build query parameters and WHERE fragments from validated filters.
        # All user-supplied values are bound as parameters to prevent SQL
        # injection; only pre-validated identifiers are interpolated.
        embedding_str = f"[{','.join(str(x) for x in embedding)}]"
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
            join_conditions.append(" AND ".join(f"v.{key} = :{key}" for key in filters))

        join_sql = " AND ".join(join_conditions)

        stmt = text(
            f"""
            WITH vector_search AS (
                SELECT {vector_select_sql},
                       embedding <-> cast(:embedding as vector) AS distance,
                       ROW_NUMBER() OVER (
                           ORDER BY
                               embedding <-> cast(:embedding as vector),
                               {self.id_field}
                       ) AS rank
                FROM {self.table_name}
                WHERE embedding <-> cast(:embedding as vector) < :distance_threshold
                {f"AND {extra_where}" if extra_where else ""}
                LIMIT :n_results
            ),
            keyword_search AS (
                SELECT {keyword_select_sql},
                       ts_rank(tsvector, plainto_tsquery('english', :query)) AS score,
                       ROW_NUMBER() OVER (
                           ORDER BY
                               ts_rank(tsvector, plainto_tsquery('english', :query)) DESC,
                               {self.id_field}
                       ) AS rank
                FROM {self.table_name}
                WHERE tsvector @@ plainto_tsquery('english', :query)
                {f"AND {extra_where}" if extra_where else ""}
                LIMIT :n_results
            )
            SELECT
                {outer_select_sql}
            FROM vector_search v
            FULL OUTER JOIN keyword_search k ON {join_sql}
            ORDER BY rrf_score DESC, {self.id_field}
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
                        "id": str(row["id"]) if row["id"] is not None else None,
                        "document": row["document"],
                        "metadata": metadata,
                        "distance": float(row["distance"]) if row["distance"] is not None else None,
                        "keyword_score": _keyword_score(row),
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

    async def count(
        self,
        session: Any = None,
        **filters: Any,
    ) -> int:
        """Count documents in the store.

        Args:
            session: Optional external SQLAlchemy async session. If provided,
                this session is reused instead of creating a new one. When an
                external session is supplied, the caller is responsible for
                committing or rolling back the transaction.
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
            if session is not None:
                result = await session.execute(stmt, params)
                count = result.scalar_one()
            else:
                async with async_session_factory() as owned_session:
                    result = await owned_session.execute(stmt, params)
                    count = result.scalar_one()
            return int(count) if count else 0
        except Exception as exc:
            logger.error("Count failed on %s: %s", self.table_name, exc)
            return 0

    @staticmethod
    def _collect_metadata_keys(documents: list[dict[str, Any]]) -> list[str]:
        """Return every metadata key used by ``documents``, in first-seen order.

        Each key is validated as a safe SQL identifier while collecting, so
        the caller can interpolate the keys into the INSERT column list.
        """
        all_meta_keys: list[str] = []
        seen_meta_keys: set[str] = set()
        for doc in documents:
            for key in doc.get("metadata", {}):
                _validate_identifier(key, "metadata key")
                if key not in seen_meta_keys:
                    seen_meta_keys.add(key)
                    all_meta_keys.append(key)
        return all_meta_keys

    @staticmethod
    def _build_values_clauses(  # noqa: PLR0913, PLR0917
        documents: list[dict[str, Any]],
        id_field: str,
        text_field: str,
        embedding_field: str,
        all_meta_keys: list[str],
        extra_fields: dict[str, Any] | None,
    ) -> tuple[list[str], dict[str, Any]]:
        """Build one VALUES row per document and its bind parameters.

        Returns the list of ``(placeholder, ...)`` clauses and the flat
        ``params`` mapping the clauses refer to. Parameter names are
        namespaced by row index so rows never collide.
        """
        values_clauses: list[str] = []
        params: dict[str, Any] = {}

        for idx, doc in enumerate(documents):
            row_placeholders = []
            for key in [id_field, text_field, embedding_field]:
                param_name = f"{key}__{idx}"
                if key == id_field:
                    params[param_name] = doc.get("id")
                elif key == embedding_field:
                    params[param_name] = f"[{','.join(str(x) for x in doc[key])}]"
                else:
                    params[param_name] = doc[key]
                row_placeholders.append(f":{param_name}")
            for meta_key in all_meta_keys:
                param_name = f"{meta_key}__{idx}"
                params[param_name] = doc.get("metadata", {}).get(meta_key)
                row_placeholders.append(f":{param_name}")
            if extra_fields:
                for extra_key, extra_val in extra_fields.items():
                    param_name = f"{extra_key}__{idx}"
                    params[param_name] = extra_val
                    row_placeholders.append(f":{param_name}")
            values_clauses.append(f"({', '.join(row_placeholders)})")

        return values_clauses, params

    async def upsert(  # noqa: PLR0913, PLR0917
        self,
        documents: list[dict[str, Any]],
        session: Any = None,
        text_field: str = "text",
        embedding_field: str = "embedding",
        id_field: str | None = None,
        extra_fields: dict[str, Any] | None = None,
    ) -> None:
        """Upsert documents into the store.

        Inserts or updates documents using PostgreSQL's ``ON CONFLICT ... DO UPDATE``
        syntax. This allows the ingestion pipeline to re-run without creating
        duplicate rows.

        Args:
            documents: List of document dicts with keys: id, text, metadata,
                embedding. Metadata keys are included as additional columns.
            session: Optional external SQLAlchemy async session. If provided,
                this session is reused instead of creating a new one. The caller
                is responsible for committing the transaction after this call.
            text_field: Name of the text column. Defaults to "text".
            embedding_field: Name of the embedding column. Defaults to "embedding".
            id_field: Name of the primary key column. Defaults to the store's
                configured ``id_field``.
            extra_fields: Additional static fields to include in every INSERT
                (e.g., ``{"owner_id": "..."}``).

        Raises:
            ValueError: If any column name contains unsafe characters.
            Exception: Re-raises database errors after logging.
        """
        _validate_identifier(text_field, "text_field")
        _validate_identifier(embedding_field, "embedding_field")
        if id_field is None:
            id_field = self.id_field
        _validate_identifier(id_field, "id_field")
        if extra_fields:
            for key in extra_fields:
                _validate_identifier(key, "extra_field")

        if not documents:
            return

        owns_session = session is None
        try:
            for doc in documents:
                _validate_embedding(
                    doc["embedding"],
                    self.embedding_dim,
                    label="document embedding",
                )

            all_meta_keys = self._collect_metadata_keys(documents)

            columns = [id_field, text_field, embedding_field]
            if extra_fields:
                columns.extend(extra_fields.keys())
            columns.extend(all_meta_keys)

            for col in columns:
                _validate_identifier(col, "upsert column")

            non_id_columns = [c for c in columns if c != id_field]
            update_str = ", ".join(f"{c} = EXCLUDED.{c}" for c in non_id_columns)

            values_clauses, params = self._build_values_clauses(  # noqa: PLR0913, PLR0917
                documents,
                id_field,
                text_field,
                embedding_field,
                all_meta_keys,
                extra_fields,
            )

            values_sql = ",\n    ".join(values_clauses)
            columns_str = ", ".join(columns)

            stmt = text(
                f"""
                INSERT INTO {self.table_name} ({columns_str})
                VALUES
                    {values_sql}
                ON CONFLICT ({id_field}) DO UPDATE SET {update_str}
            """
            )

            if owns_session:
                async with async_session_factory() as owned_session:
                    await owned_session.execute(stmt, params)
                    await owned_session.commit()
            else:
                await session.execute(stmt, params)
            logger.info("Upserted %d documents to %s.", len(documents), self.table_name)
        except Exception as exc:
            logger.error("Upsert failed on %s: %s", self.table_name, exc)
            raise
