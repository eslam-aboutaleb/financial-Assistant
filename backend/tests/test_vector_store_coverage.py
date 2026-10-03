"""Coverage tests for app.rag.vector_store uncovered paths."""

from __future__ import annotations

from unittest.mock import patch

import pytest


class TestVectorStore:
    def test_get_vector_store_unsupported_provider(self):
        from app.config import Settings
        from app.rag.vector_store import get_vector_store

        with patch("app.rag.vector_store.get_settings") as mock_get:
            mock_settings = Settings(vector_store_provider="unsupported")
            mock_get.return_value = mock_settings
            with pytest.raises(ValueError, match="Unsupported vector store provider"):
                get_vector_store(table_name="test", id_field="id")
