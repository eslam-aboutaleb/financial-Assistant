"""
Embedding job worker for the OmniCare backend.

This module provides an outbox pattern for decoupling claim insertion from
embedding generation. When a claim is submitted, a job is written to the
``embedding_jobs`` table. A background worker picks up pending jobs, generates
embeddings, and upserts them into the vector store.

This prevents the claim submission path from being blocked by external
embedding API latency or failures.

Invariant for anything that writes an ``embedding_jobs`` row
------------------------------------------------------------
A job row must be committed in the **same transaction** as the claim it refers to,
or written through this outbox by a caller that has already committed that claim.

The reason is that ``embedding_jobs.claim_uuid`` has no foreign key to ``claims``,
so the database will not stop an orphan job from appearing. An enqueue that commits
on its own session races the claim transaction: if the claim transaction rolls back
afterwards, the job survives, points at a claim that does not exist, and the worker
then upserts a claim index entry for a row nobody can ever read.

Therefore:

- ``enqueue_embedding_job(session=...)`` only flushes. Pass the caller's session.
- ``enqueue_embedding_job()`` with no session opens its own and commits. Use it only
  where the claim is already durable.
- ``submit_claim`` adds the ``EmbeddingJob`` to the caller's session directly.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.rag.embedding import EmbeddingFactory
from app.rag.vector_store import get_vector_store

if TYPE_CHECKING:
    from app.models.embedding_job import EmbeddingJob

logger = logging.getLogger(__name__)

RETRY_SCHEDULE = [
    timedelta(minutes=1),
    timedelta(minutes=5),
    timedelta(minutes=30),
]
MAX_ATTEMPTS = 4


def _claim_jobs(jobs: list[EmbeddingJob], worker_id: str, now: datetime) -> None:
    """Transition claimed jobs to ``processing`` and stamp the lock.

    A failed job is first reset to ``pending`` so its retry bookkeeping
    starts clean; the lock columns then record which worker claimed it
    and when, for ``reclaim_stale_jobs``.
    """
    for job in jobs:
        if job.status == "failed":
            job.status = "pending"
            job.status_detail = None
            job.next_retry_at = None
        job.status = "processing"
        job.locked_at = now
        job.locked_by = worker_id


async def enqueue_embedding_job(  # noqa: PLR0913, PLR0917
    claim_uuid: uuid.UUID,
    claim_id: str,
    owner_id: uuid.UUID,
    claim_type: str,
    description: str,
    policy_number: str,
    claim_status: str,
    session: AsyncSession | None = None,
) -> None:
    """Add an embedding job for a newly submitted claim.

    When ``session`` is supplied the job is only added and flushed; the caller owns
    the commit, so the job and the claim land in one transaction. When it is omitted
    this function opens its own session and commits.

    Callers that are writing a claim must pass their session. See the module
    docstring for why.

    Args:
        claim_uuid: The claim's UUID primary key.
        claim_id: The unique claim identifier (e.g., "CLM-8821").
        owner_id: UUID of the claim owner.
        claim_type: Type of claim.
        description: Claim description text.
        policy_number: Associated policy number.
        claim_status: Current business status of the claim.
        session: Optional caller-owned session. Not committed when provided.
    """
    from app.models.embedding_job import EmbeddingJob  # noqa: PLC0415

    job = EmbeddingJob(
        claim_uuid=claim_uuid,
        claim_id=claim_id,
        owner_id=owner_id,
        claim_type=claim_type,
        description=description,
        policy_number=policy_number,
        claim_status=claim_status,
        status="pending",
        status_detail="pending",
    )
    try:
        if session is not None:
            session.add(job)
            await session.flush()
        else:
            async with async_session_factory() as owned_session:
                owned_session.add(job)
                await owned_session.commit()
        logger.info("Enqueued embedding job for claim '%s'.", claim_id)
    except Exception as exc:
        logger.exception("Failed to enqueue embedding job for claim '%s': %s", claim_id, exc)


async def process_pending_jobs(limit: int = 10, worker_id: str | None = None) -> int:
    """Process pending embedding jobs.

    Fetches up to ``limit`` pending jobs, generates embeddings, and upserts
    them into the vector store. Failed jobs are marked with an error detail
    for retry.

    Claimed jobs are stamped with ``locked_at``/``locked_by`` for the whole
    processing transaction. A worker that dies mid-pass therefore leaves a
    visible lock, which ``reclaim_stale_jobs`` later resets.

    Args:
        limit: Maximum number of jobs to process in one batch.
        worker_id: Identity stamped into ``locked_by``. Defaults to
            ``settings.worker_id``.

    Returns:
        int: Number of jobs successfully processed.
    """
    from sqlalchemy import select  # noqa: PLC0415

    from app.config import settings  # noqa: PLC0415
    from app.models.embedding_job import EmbeddingJob  # noqa: PLC0415

    from app.models.claim import Claim  # noqa: PLC0415

    if worker_id is None:
        worker_id = settings.worker_id

    processed = 0
    async with async_session_factory() as session:
        now = datetime.now(UTC)
        result = await session.execute(
            select(EmbeddingJob)
            .where(
                (EmbeddingJob.status == "pending")
                | (
                    (EmbeddingJob.status == "failed")
                    & (EmbeddingJob.next_retry_at <= now)
                    & (EmbeddingJob.retry_count < EmbeddingJob.max_attempts)
                )
            )
            .order_by(EmbeddingJob.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        jobs = result.scalars().all()

        _claim_jobs(jobs, worker_id, now)
        await session.commit()

        for job in jobs:
            try:
                claim_amount = await session.scalar(
                    select(Claim.amount).where(Claim.claim_id == job.claim_id)
                )
                claim_amount = claim_amount if claim_amount is not None else 0.0

                embed_fn = EmbeddingFactory.get_embedding_function()
                text_content = f"Claim {job.claim_id}: {job.claim_type} - {job.description}"
                embeddings = await embed_fn([text_content])
                embedding = embeddings[0]

                store = get_vector_store(table_name="claims", id_field="id")
                await store.upsert(
                    documents=[
                        {
                            "id": str(job.claim_uuid),
                            "text": text_content,
                            "embedding": embedding,
                            "metadata": {
                                "claim_id": job.claim_id,
                                "policy_number": job.policy_number,
                                "claim_type": job.claim_type,
                                "status": job.claim_status,
                                "amount": float(claim_amount),
                                "description": job.description,
                                "owner_id": str(job.owner_id),
                            },
                        }
                    ],
                )

                job.status = "completed"
                job.completed_at = datetime.now(UTC)
                await session.commit()
                processed += 1
                logger.info("Processed embedding job for claim '%s'.", job.claim_id)
            except Exception as exc:
                job.retry_count += 1
                if job.retry_count >= job.max_attempts:
                    job.status = "dead_letter"
                    job.status_detail = f"Exhausted {job.max_attempts} attempts: {exc}"
                    job.next_retry_at = None
                    job.locked_at = None
                    job.locked_by = None
                else:
                    backoff = RETRY_SCHEDULE[min(job.retry_count - 1, len(RETRY_SCHEDULE) - 1)]
                    job.next_retry_at = datetime.now(UTC) + backoff
                    job.status = "failed"
                    job.status_detail = str(exc)
                    job.locked_at = None
                    job.locked_by = None
                await session.commit()
                logger.error(
                    "Embedding job failed for claim '%s' (retry %d): %s",
                    job.claim_id,
                    job.retry_count,
                    exc,
                )

    return processed


async def reclaim_stale_jobs(stale_after_seconds: float | None = None) -> int:
    """Reset jobs abandoned in ``processing`` back to ``pending``.

    A drainer that dies mid-upsert leaves its rows locked in
    ``processing`` forever: the claim query only selects ``pending``
    or retry-due ``failed`` rows, so no live worker can pick them up
    again. This reclaims rows whose ``locked_at`` is older than
    ``stale_after_seconds`` — or whose lock timestamp is NULL, which
    marks rows locked before the column existed — so a replacement
    worker can process them.

    Args:
        stale_after_seconds: Lock age in seconds that counts as
            abandoned. Defaults to ``settings.job_stale_after_seconds``.

    Returns:
        int: Number of jobs reclaimed.
    """
    from sqlalchemy import select  # noqa: PLC0415

    from app.config import settings  # noqa: PLC0415
    from app.models.embedding_job import EmbeddingJob  # noqa: PLC0415

    if stale_after_seconds is None:
        stale_after_seconds = settings.job_stale_after_seconds

    cutoff = datetime.now(UTC) - timedelta(seconds=stale_after_seconds)
    reclaimed = 0
    async with async_session_factory() as session:
        result = await session.execute(
            select(EmbeddingJob)
            .where(
                (EmbeddingJob.status == "processing")
                & (EmbeddingJob.locked_at.is_(None) | (EmbeddingJob.locked_at <= cutoff))
            )
            .with_for_update(skip_locked=True)
        )
        stale_jobs = result.scalars().all()
        for job in stale_jobs:
            job.status = "pending"
            job.status_detail = None
            job.locked_at = None
            job.locked_by = None
            reclaimed += 1
        if reclaimed:
            await session.commit()

    if reclaimed:
        logger.info("Reclaimed %d stale embedding job(s).", reclaimed)
    return reclaimed
