"""
Embedding job worker for the OmniCare backend.

This module provides an outbox pattern for decoupling claim insertion from
embedding generation. When a claim is submitted, a job is written to the
``embedding_jobs`` table. A background worker picks up pending jobs, generates
embeddings, and upserts them into the vector store.

This prevents the claim submission path from being blocked by external
embedding API latency or failures.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from app.database import async_session_factory
from app.rag.embedding import EmbeddingFactory
from app.rag.vector_store import get_vector_store

logger = logging.getLogger(__name__)


async def enqueue_embedding_job(  # noqa: PLR0913, PLR0917
    claim_id: str,
    owner_id: uuid.UUID,
    claim_type: str,
    description: str,
    policy_number: str,
    status: str,
) -> None:
    """Create an embedding job for a newly submitted claim.

    This is called within the claim submission transaction to ensure the
    job is created atomically with the claim.

    Args:
        claim_id: The unique claim identifier.
        owner_id: UUID of the claim owner.
        claim_type: Type of claim.
        description: Claim description text.
        policy_number: Associated policy number.
        status: Current claim status.
    """
    from app.models.embedding_job import EmbeddingJob  # noqa: PLC0415

    job = EmbeddingJob(
        claim_id=claim_id,
        owner_id=owner_id,
        claim_type=claim_type,
        description=description,
        policy_number=policy_number,
        status=status,
        status_detail="pending",
    )
    try:
        async with async_session_factory() as session:
            session.add(job)
            await session.commit()
        logger.info("Enqueued embedding job for claim '%s'.", claim_id)
    except Exception as exc:
        logger.exception("Failed to enqueue embedding job for claim '%s': %s", claim_id, exc)


async def process_pending_jobs(limit: int = 10) -> int:
    """Process pending embedding jobs.

    Fetches up to ``limit`` pending jobs, generates embeddings, and upserts
    them into the vector store. Failed jobs are marked with an error detail
    for retry.

    Args:
        limit: Maximum number of jobs to process in one batch.

    Returns:
        int: Number of jobs successfully processed.
    """
    from sqlalchemy import select  # noqa: PLC0415

    from app.models.embedding_job import EmbeddingJob  # noqa: PLC0415

    processed = 0
    async with async_session_factory() as session:
        result = await session.execute(
            select(EmbeddingJob)
            .where(EmbeddingJob.status == "pending")
            .order_by(EmbeddingJob.created_at)
            .limit(limit)
        )
        jobs = result.scalars().all()

        for job in jobs:
            job.status = "processing"
            await session.commit()

            try:
                embed_fn = EmbeddingFactory.get_embedding_function()
                text_content = f"Claim {job.claim_id}: {job.claim_type} - {job.description}"
                embeddings = await embed_fn([text_content])
                embedding = embeddings[0]

                store = get_vector_store(table_name="claims", id_field="id")
                await store.upsert(
                    documents=[
                        {
                            "id": str(job.owner_id),
                            "text": text_content,
                            "embedding": embedding,
                            "metadata": {
                                "claim_id": job.claim_id,
                                "policy_number": job.policy_number,
                                "claim_type": job.claim_type,
                                "status": job.status,
                                "amount": 0.0,
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
                job.status = "failed"
                job.status_detail = str(exc)
                job.retry_count += 1
                await session.commit()
                logger.error(
                    "Embedding job failed for claim '%s' (retry %d): %s",
                    job.claim_id,
                    job.retry_count,
                    exc,
                )

    return processed
