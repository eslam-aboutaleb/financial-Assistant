"""add_retry_state_to_embedding_jobs

Revision ID: 8aef16d71c459439
Revises: d4e5f6a7b8c9
Create Date: 2026-10-02 11:12:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8aef16d71c459439"
down_revision: str | Sequence[str] | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "embedding_jobs",
        sa.Column("next_retry_at", TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "embedding_jobs",
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="4"),
    )

    op.execute("UPDATE embedding_jobs SET max_attempts = 4 WHERE max_attempts IS NULL")

    op.execute(
        "UPDATE embedding_jobs SET next_retry_at = now() "
        "WHERE status = 'failed' AND next_retry_at IS NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("embedding_jobs", "max_attempts")
    op.drop_column("embedding_jobs", "next_retry_at")
