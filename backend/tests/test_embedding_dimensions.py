"""Tests for app.rag.embedding_dimensions.

Covers the provider dimension table and the warning-and-fallback path for
models that are not registered, which is the corner case a deployment hits
when it swaps in an embedding provider the table does not know about yet.
"""

from __future__ import annotations

import logging

from app.rag.embedding_dimensions import get_embedding_dimension


class TestEmbeddingDimensions:
    def test_known_models_resolve_to_their_dimensions(self):
        assert get_embedding_dimension("text-embedding-3-small") == 1536
        assert get_embedding_dimension("text-embedding-3-large") == 3072
        assert get_embedding_dimension("text-embedding-ada-002") == 1536

    def test_explicit_model_overrides_the_configured_default(self):
        assert get_embedding_dimension("text-embedding-3-large") == 3072

    def test_unknown_model_warns_and_falls_back(self, caplog):
        with caplog.at_level(logging.WARNING, logger="app.rag.embedding_dimensions"):
            dimension = get_embedding_dimension("brand-new-model")

        assert dimension == 1536
        assert any(
            "No embedding dimension registered for model 'brand-new-model'" in record.message
            for record in caplog.records
        )

    def test_default_uses_the_configured_embedding_model(self):
        from app.config import settings

        assert get_embedding_dimension() == get_embedding_dimension(settings.embedding_model)
