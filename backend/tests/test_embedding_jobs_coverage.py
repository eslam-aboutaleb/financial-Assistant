"""Coverage tests for app.rag.embedding_jobs uncovered paths."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestEmbeddingJobs:
    @pytest.mark.asyncio
    async def test_enqueue_embedding_job_exception_logged(self):
        from app.rag.embedding_jobs import enqueue_embedding_job

        with patch("app.rag.embedding_jobs.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__.side_effect = Exception("DB down")
            with patch("app.rag.embedding_jobs.logger") as mock_logger:
                await enqueue_embedding_job(
                    claim_uuid=uuid.UUID("00000000-0000-0000-0000-000000000001"),
                    claim_id="CLM-9999",
                    owner_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
                    claim_type="Water Damage",
                    description="Test",
                    policy_number="POL-1092",
                    claim_status="Submitted",
                )
                mock_logger.exception.assert_called()

    @pytest.mark.asyncio
    async def test_enqueue_embedding_job_success(self):
        from app.rag.embedding_jobs import enqueue_embedding_job

        with patch("app.rag.embedding_jobs.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_factory.return_value.__aenter__.return_value = mock_session
            await enqueue_embedding_job(
                claim_uuid=uuid.UUID("00000000-0000-0000-0000-000000000001"),
                claim_id="CLM-9999",
                owner_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
                claim_type="Water Damage",
                description="Test",
                policy_number="POL-1092",
                claim_status="Submitted",
            )
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()
