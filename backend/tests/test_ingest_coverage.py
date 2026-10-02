"""Coverage tests for app.rag.ingest uncovered paths."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestIngest:
    def test_sliding_window_chunk_empty_text(self):
        from app.rag.ingest import sliding_window_chunk

        assert sliding_window_chunk("") == []
        assert sliding_window_chunk("   ") == []

    def test_chunk_policy_document_file_not_found(self):
        from app.rag.ingest import chunk_policy_document

        result = chunk_policy_document("/nonexistent/path/policy.md")
        assert result == []

    def test_chunk_policy_document_no_title_match(self):
        from app.rag.ingest import chunk_policy_document

        text = "Some content without title"
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(text)
            path = f.name
        try:
            result = chunk_policy_document(path)
            assert len(result) > 0
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_ingest_policy_no_path_configured(self):
        from app.config import Settings
        from app.rag.ingest import ingest_policy

        with patch("app.rag.ingest.get_settings") as mock_get_settings:
            mock_settings = Settings(policy_file_path="")
            mock_get_settings.return_value = mock_settings
            count = await ingest_policy()
        assert count == 0

    @pytest.mark.asyncio
    async def test_ingest_policy_file_not_found_returns_zero(self):
        from app.rag.ingest import ingest_policy

        with patch("app.rag.ingest.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.policy_file_path = "/nonexistent/policy.md"
            mock_get_settings.return_value = mock_settings
            count = await ingest_policy()
        assert count == 0

    def test_ingest_main_block(self):
        with patch("app.rag.ingest.ingest_policy", new_callable=AsyncMock) as mock_ingest:
            mock_ingest.return_value = 0
            import app.rag.ingest as ingest_module

            original_name = ingest_module.__name__
            try:
                ingest_module.__name__ = "__main__"
                import asyncio
                asyncio.run(ingest_module.ingest_policy())
            finally:
                ingest_module.__name__ = original_name
