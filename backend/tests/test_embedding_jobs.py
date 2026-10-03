"""
Tests for embedding job retry behavior with exponential backoff and dead-letter state.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rag.embedding_jobs import MAX_ATTEMPTS, RETRY_SCHEDULE, process_pending_jobs


def _make_job(**overrides):
    defaults = {
        "id": uuid.uuid4(),
        "claim_id": "CLM-1",
        "claim_uuid": uuid.uuid4(),
        "owner_id": uuid.uuid4(),
        "claim_type": "Water Damage",
        "description": "Pipe burst",
        "policy_number": "POL-1",
        "claim_status": "Submitted",
        "status": "pending",
        "status_detail": "pending",
        "retry_count": 0,
        "next_retry_at": None,
        "max_attempts": 4,
        "created_at": datetime.now(UTC),
        "completed_at": None,
    }
    defaults.update(overrides)
    return defaults


def _make_session(jobs):
    mock_session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = jobs
    mock_session.execute.return_value = result
    mock_session.scalar.return_value = 0.0
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    return mock_session


@pytest.mark.asyncio
async def test_failed_job_retries_with_backoff():
    """Failing a job 3 times keeps it failed with a future next_retry_at."""
    job = _make_job()
    job_mock = MagicMock(**job)
    mock_session = _make_session([job_mock])
    embed_fn = AsyncMock(return_value=[[0.0] * 1536])

    with (
        patch("app.rag.embedding_jobs.async_session_factory") as mock_factory,
        patch(
            "app.rag.embedding_jobs.EmbeddingFactory.get_embedding_function", return_value=embed_fn
        ),
        patch("app.rag.embedding_jobs.get_vector_store", return_value=AsyncMock()),
    ):
        mock_factory.return_value.__aenter__.return_value = mock_session

        for _ in range(3):
            embed_fn.side_effect = [Exception("embed error")]
            await process_pending_jobs(limit=10)

    assert job_mock.status == "failed"
    assert job_mock.retry_count == 3
    assert job_mock.next_retry_at is not None
    assert job_mock.next_retry_at > datetime.now(UTC)


@pytest.mark.asyncio
async def test_failed_job_moves_to_dead_letter_after_max_attempts():
    """Failing a job 4 times moves it to dead_letter."""
    job = _make_job()
    job_mock = MagicMock(**job)
    mock_session = _make_session([job_mock])
    embed_fn = AsyncMock(return_value=[[0.0] * 1536])

    with (
        patch("app.rag.embedding_jobs.async_session_factory") as mock_factory,
        patch(
            "app.rag.embedding_jobs.EmbeddingFactory.get_embedding_function", return_value=embed_fn
        ),
        patch("app.rag.embedding_jobs.get_vector_store", return_value=AsyncMock()),
    ):
        mock_factory.return_value.__aenter__.return_value = mock_session

        for _ in range(4):
            embed_fn.side_effect = [Exception("embed error")]
            await process_pending_jobs(limit=10)

    assert job_mock.status == "dead_letter"
    assert job_mock.retry_count == 4
    assert job_mock.next_retry_at is None
    assert "Exhausted 4 attempts" in job_mock.status_detail


@pytest.mark.asyncio
async def test_retriable_failed_job_is_processed_after_backoff():
    """A failed job whose next_retry_at has passed is retried and can succeed."""
    past_time = datetime.now(UTC) - timedelta(minutes=2)
    job = _make_job(
        status="failed",
        retry_count=1,
        next_retry_at=past_time,
        max_attempts=4,
    )
    job_mock = MagicMock(**job)
    mock_session = _make_session([job_mock])
    embed_fn = AsyncMock(return_value=[[0.0] * 1536])

    with (
        patch("app.rag.embedding_jobs.async_session_factory") as mock_factory,
        patch(
            "app.rag.embedding_jobs.EmbeddingFactory.get_embedding_function", return_value=embed_fn
        ),
        patch("app.rag.embedding_jobs.get_vector_store", return_value=AsyncMock()),
    ):
        mock_factory.return_value.__aenter__.return_value = mock_session
        processed = await process_pending_jobs(limit=10)

    assert processed == 1
    assert job_mock.status == "completed"


@pytest.mark.asyncio
async def test_dead_letter_job_is_never_selected():
    """A dead_letter job is never picked up by the worker."""
    mock_session = _make_session([])

    with (
        patch("app.rag.embedding_jobs.async_session_factory") as mock_factory,
    ):
        mock_factory.return_value.__aenter__.return_value = mock_session
        processed = await process_pending_jobs(limit=10)

    assert processed == 0
    mock_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_retry_schedule_constants():
    """Retry schedule has the expected number of intervals and MAX_ATTEMPTS matches."""
    assert len(RETRY_SCHEDULE) == MAX_ATTEMPTS - 1
    assert RETRY_SCHEDULE[0] == timedelta(minutes=1)
    assert RETRY_SCHEDULE[1] == timedelta(minutes=5)
    assert RETRY_SCHEDULE[2] == timedelta(minutes=30)


@pytest.mark.asyncio
async def test_process_pending_jobs_uses_claim_status_in_metadata():
    """process_pending_jobs() stores job.claim_status in vector index metadata, not job.status."""
    job = _make_job(claim_status="Denied")
    job_mock = MagicMock(**job)
    mock_session = _make_session([job_mock])
    embed_fn = AsyncMock(return_value=[[0.0] * 1536])
    captured_metadata = {}

    async def fake_upsert(documents, session=None):
        captured_metadata.update(documents[0]["metadata"])

    mock_store = AsyncMock()
    mock_store.upsert.side_effect = fake_upsert

    with (
        patch("app.rag.embedding_jobs.async_session_factory") as mock_factory,
        patch(
            "app.rag.embedding_jobs.EmbeddingFactory.get_embedding_function", return_value=embed_fn
        ),
        patch("app.rag.embedding_jobs.get_vector_store", return_value=mock_store),
    ):
        mock_factory.return_value.__aenter__.return_value = mock_session
        processed = await process_pending_jobs(limit=10)

    assert processed == 1
    assert captured_metadata["status"] == "Denied"


@pytest.mark.asyncio
async def test_claimed_jobs_are_stamped_with_lock_fields():
    """Claimed jobs record which worker took them and when."""
    job = _make_job()
    job_mock = MagicMock(**job)
    mock_session = _make_session([job_mock])
    embed_fn = AsyncMock(return_value=[[0.0] * 1536])

    with (
        patch("app.rag.embedding_jobs.async_session_factory") as mock_factory,
        patch(
            "app.rag.embedding_jobs.EmbeddingFactory.get_embedding_function", return_value=embed_fn
        ),
        patch("app.rag.embedding_jobs.get_vector_store", return_value=AsyncMock()),
    ):
        mock_factory.return_value.__aenter__.return_value = mock_session
        await process_pending_jobs(limit=10, worker_id="worker-1")

    assert job_mock.status == "completed"
    assert job_mock.locked_by == "worker-1"
    assert job_mock.locked_at is not None


@pytest.mark.asyncio
async def test_max_attempts_comes_from_the_database_column():
    """The DB column is authoritative: a job with max_attempts=2 dead-letters after 2 failures."""
    job = _make_job(max_attempts=2)
    job_mock = MagicMock(**job)
    mock_session = _make_session([job_mock])
    embed_fn = AsyncMock(return_value=[[0.0] * 1536])

    with (
        patch("app.rag.embedding_jobs.async_session_factory") as mock_factory,
        patch(
            "app.rag.embedding_jobs.EmbeddingFactory.get_embedding_function", return_value=embed_fn
        ),
        patch("app.rag.embedding_jobs.get_vector_store", return_value=AsyncMock()),
    ):
        mock_factory.return_value.__aenter__.return_value = mock_session

        for _ in range(2):
            embed_fn.side_effect = [Exception("embed error")]
            await process_pending_jobs(limit=10)

    assert job_mock.status == "dead_letter"
    assert job_mock.retry_count == 2
    assert "Exhausted 2 attempts" in job_mock.status_detail


@pytest.mark.asyncio
async def test_failed_job_releases_its_lock():
    """A failed job clears its lock so a later pass can reclaim it."""
    job = _make_job()
    job_mock = MagicMock(**job)
    mock_session = _make_session([job_mock])
    embed_fn = AsyncMock(return_value=[[0.0] * 1536])

    with (
        patch("app.rag.embedding_jobs.async_session_factory") as mock_factory,
        patch(
            "app.rag.embedding_jobs.EmbeddingFactory.get_embedding_function", return_value=embed_fn
        ),
        patch("app.rag.embedding_jobs.get_vector_store", return_value=AsyncMock()),
    ):
        mock_factory.return_value.__aenter__.return_value = mock_session
        embed_fn.side_effect = [Exception("embed error")]
        await process_pending_jobs(limit=10, worker_id="worker-1")

    assert job_mock.status == "failed"
    assert job_mock.locked_at is None
    assert job_mock.locked_by is None


def _make_reclaim_session(jobs):
    mock_session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = jobs
    mock_session.execute.return_value = result
    mock_session.commit = AsyncMock()
    return mock_session


@pytest.mark.asyncio
async def test_reclaim_stale_jobs_resets_abandoned_locks():
    """A job the query returns as stale is reset to pending.

    The mock session cannot evaluate the SQL ``WHERE`` clause, so it
    returns only the row a real database would select; the filter
    itself is covered by the Tier B integration test.
    """
    from app.rag.embedding_jobs import reclaim_stale_jobs

    stale = _make_job(
        status="processing",
        locked_at=datetime.now(UTC) - timedelta(hours=1),
        locked_by="dead-worker",
    )
    stale_mock = MagicMock(**stale)
    mock_session = _make_reclaim_session([stale_mock])

    with patch("app.rag.embedding_jobs.async_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__.return_value = mock_session
        reclaimed = await reclaim_stale_jobs(stale_after_seconds=300)

    assert reclaimed == 1
    assert stale_mock.status == "pending"
    assert stale_mock.locked_at is None
    assert stale_mock.locked_by is None
    assert stale_mock.status_detail is None
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_reclaim_stale_jobs_treats_null_lock_as_stale():
    """A NULL locked_at predates the column and counts as abandoned."""
    from app.rag.embedding_jobs import reclaim_stale_jobs

    job = _make_job(status="processing", locked_at=None, locked_by="unknown")
    job_mock = MagicMock(**job)
    mock_session = _make_reclaim_session([job_mock])

    with patch("app.rag.embedding_jobs.async_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__.return_value = mock_session
        reclaimed = await reclaim_stale_jobs(stale_after_seconds=300)

    assert reclaimed == 1
    assert job_mock.status == "pending"
    assert job_mock.locked_by is None
