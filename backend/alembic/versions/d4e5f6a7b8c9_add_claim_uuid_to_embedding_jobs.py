"""add_claim_uuid_to_embedding_jobs

Revision ID: d4e5f6a7b8c9
Revises: 822df1979a12
Create Date: 2026-09-30 07:37:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "822df1979a12"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "embedding_jobs",
        sa.Column("claim_uuid", UUID(as_uuid=True), nullable=False),
    )
    op.create_index(
        "ix_embedding_jobs_claim_uuid",
        "embedding_jobs",
        ["claim_uuid"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_embedding_jobs_claim_uuid", table_name="embedding_jobs")
    op.drop_column("embedding_jobs", "claim_uuid")
