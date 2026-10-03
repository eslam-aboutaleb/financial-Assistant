"""add_job_lock_columns

Revision ID: c4d5e6f7a8b9
Revises: b7c2d4e6f8a0
Create Date: 2026-10-03

``embedding_jobs`` rows transition to ``processing`` inside the drainer, but
nothing recorded *which* worker claimed a job or *when*. A worker that died
mid-upsert left its rows stuck in ``processing`` forever: the claim query only
selects ``pending`` or retry-due ``failed`` rows, so no live worker could ever
pick them up again.

``locked_at``/``locked_by`` record the claim, and the drainer reclaims rows
whose lock is older than ``job_stale_after_seconds``. Rows already in
``processing`` when this migration runs predate the columns, so their
``locked_by`` is backfilled as ``unknown``; their ``locked_at`` stays NULL and
the reclaim treats a NULL lock timestamp as stale.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: str | Sequence[str] | None = "b7c2d4e6f8a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the lock columns and backfill the worker identity."""
    op.add_column(
        "embedding_jobs",
        sa.Column("locked_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "embedding_jobs",
        sa.Column("locked_by", sa.String, nullable=True),
    )
    op.execute(
        "UPDATE embedding_jobs SET locked_by = 'unknown' "
        "WHERE status = 'processing' AND locked_by IS NULL"
    )


def downgrade() -> None:
    """Drop the lock columns."""
    op.drop_column("embedding_jobs", "locked_by")
    op.drop_column("embedding_jobs", "locked_at")
