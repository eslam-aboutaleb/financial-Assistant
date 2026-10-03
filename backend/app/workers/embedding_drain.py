"""
Outbox drainer for the ``embedding_jobs`` table.

Runs as its own process so embedding generation never blocks an API request. The API
writes a job row in the same transaction as the claim; this worker claims pending jobs
with ``FOR UPDATE SKIP LOCKED``, generates the embedding, upserts it into pgvector, and
marks the job ``completed``.

Run it directly:

    python -m app.workers.embedding_drain

Configuration (all optional, validated by ``app.config.Settings``):

    EMBEDDING_DRAIN_INTERVAL_SECONDS  seconds to sleep when the queue is empty
    EMBEDDING_DRAIN_BATCH_SIZE       jobs claimed per pass

Multiple drainers can run concurrently: ``SKIP LOCKED`` keeps two workers from
processing the same job, so this scales horizontally without coordination.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
import sys

from app.config import settings
from app.rag.embedding_jobs import process_pending_jobs, reclaim_stale_jobs

logger = logging.getLogger("omnicare.embedding_drain")


def _interval_seconds() -> float:
    """Return the validated sleep duration between empty passes."""
    return settings.embedding_drain_interval_seconds


def _batch_size() -> int:
    """Return the validated number of jobs claimed per pass."""
    return settings.embedding_drain_batch_size


async def drain_forever(stop: asyncio.Event | None = None) -> None:
    """Process embedding jobs until the stop event is set.

    A failing pass is logged and retried on the next tick rather than terminating the
    worker: a transient embedding API outage should not require a restart.

    Args:
        stop: Optional event that ends the loop when set.
    """
    stop = stop or asyncio.Event()
    interval = _interval_seconds()
    batch = _batch_size()

    logger.info(
        "Embedding drainer started (interval=%ss, batch=%d, embedding_model=%s).",
        interval,
        batch,
        settings.embedding_model,
    )

    while not stop.is_set():
        try:
            reclaimed = await reclaim_stale_jobs()
            if reclaimed:
                logger.info("Reclaimed %d stale embedding job(s).", reclaimed)
            processed = await process_pending_jobs(limit=batch, worker_id=settings.worker_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Embedding drain pass failed; retrying on the next tick.")
            processed = 0

        if processed:
            logger.info("Processed %d embedding job(s).", processed)
            continue

        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=interval)

    logger.info("Embedding drainer stopped.")


def _install_signal_handlers(stop: asyncio.Event) -> None:
    """Ask the loop to stop on SIGINT/SIGTERM so in-flight work can finish."""
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)


async def _main() -> None:
    """Entry point: drain until a termination signal arrives."""
    stop = asyncio.Event()
    _install_signal_handlers(stop)
    await drain_forever(stop)


def main() -> int:
    """Console entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_main())
    return 0


if __name__ == "__main__":
    sys.exit(main())
