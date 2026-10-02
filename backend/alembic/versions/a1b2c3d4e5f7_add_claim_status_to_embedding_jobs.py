"""add_claim_status_to_embedding_jobs

Revision ID: a1b2c3d4e5f7
Revises: f6a7b8c9d0e1
Create Date: 2026-10-02 11:11:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f7"
down_revision: str | Sequence[str] | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "embedding_jobs",
        sa.Column("claim_status", sa.String(64), nullable=False, server_default="unknown"),
    )
    op.execute(
        """
        UPDATE embedding_jobs ej
        SET claim_status = COALESCE(c.status, 'unknown')
        FROM claims c
        WHERE c.id = ej.claim_uuid
        """
    )
    op.alter_column("embedding_jobs", "claim_status", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("embedding_jobs", "claim_status")
