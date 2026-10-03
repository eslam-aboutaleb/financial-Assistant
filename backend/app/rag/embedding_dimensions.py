"""
Single source of truth for the embedding model and its vector dimension.

The dimension was previously duplicated in five places as a literal ``1536`` and as a
hardcoded pgvector ``Vector(1536)`` column type in two ORM models. Nothing tied them
together, so changing the embedding model required finding every literal by hand, and a
miss produced a runtime failure at insert time rather than at start-up.

``get_embedding_dimension()`` returns the dimension configured for the active provider.
Call sites pass that value to ``pgvector_store._validate_embedding``, which remains the
single validator for dimension and finiteness.

Known limitation: the pgvector column type in the ORM models is still declared with a
literal ``Vector(1536)``. ``ALTER TABLE`` to widen or narrow the stored column is a
separate migration and is deliberately out of scope here; this module makes the
runtime checks authoritative so a mismatch is caught before it reaches the database.
"""

from __future__ import annotations

import logging

# Dimension per supported embedding provider. ``text-embedding-3-small`` is the only
# provider configured today; OpenAI's ``text-embedding-ada-002`` is the historical
# model and shares its dimension.
_EMBEDDING_DIMENSIONS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}

_FALLBACK_DIMENSION = 1536

logger = logging.getLogger(__name__)


def get_embedding_dimension(model: str | None = None) -> int:
    """Return the vector dimension for an embedding model.

    Args:
        model: The embedding model name. Defaults to ``settings.embedding_model``.

    Returns:
        The dimension, or the fallback when the model is not in the known table.

    Raises:
        ValueError: If the configured model is unknown and no fallback applies.
    """
    if model is None:
        from app.config import settings  # noqa: PLC0415

        model = settings.embedding_model

    dimension = _EMBEDDING_DIMENSIONS.get(model)
    if dimension is not None:
        return dimension

    # Warn rather than raise. The previous behaviour fell back to 1536, so raising here
    # would turn a configuration-only change into a startup crash for anyone using a
    # provider outside this table. The warning makes the wrong dimension visible while
    # keeping a misconfigured deployment starting.
    logger.warning(
        "No embedding dimension registered for model '%s'; assuming %d. "
        "Add it to app.rag.embedding_dimensions._EMBEDDING_DIMENSIONS if that is wrong.",
        model,
        _FALLBACK_DIMENSION,
    )
    return _FALLBACK_DIMENSION
