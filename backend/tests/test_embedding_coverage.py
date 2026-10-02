"""Coverage tests for app.rag.embedding uncovered paths."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestEmbedding:
    def test_get_embedding_function_returns_callable(self):
        from app.rag.embedding import EmbeddingFactory

        func = EmbeddingFactory.get_embedding_function()
        assert callable(func)

    def test_embedding_factory_returns_function_with_model_name(self):
        from app.rag.embedding import EmbeddingFactory

        with patch("app.rag.embedding.get_settings") as mock_get:
            mock_settings = MagicMock()
            mock_settings.embedding_model = "custom-model"
            mock_get.return_value = mock_settings
            func = EmbeddingFactory.get_embedding_function()
            assert func.model_name == "custom-model"