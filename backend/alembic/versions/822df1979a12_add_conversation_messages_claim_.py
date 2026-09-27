"""add_conversation_messages_claim_submissions_embedding_jobs

Revision ID: 822df1979a12
Revises: a1b2c3d4e5f6
Create Date: 2026-09-27 15:19:06.005140

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "822df1979a12"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "conversation_messages",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "conversation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "timestamp", TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Index("ix_conversation_messages_conversation_id", "conversation_id"),
    )
    op.create_table(
        "claim_submissions",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("confirmation_token", sa.String(64), unique=True, nullable=False),
        sa.Column("claim_data", JSONB, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("expires_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "created_at", TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Index("ix_claim_submissions_user_id", "user_id"),
        sa.Index("ix_claim_submissions_status", "status"),
    )
    op.create_table(
        "embedding_jobs",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("claim_id", sa.String, nullable=False),
        sa.Column(
            "owner_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("claim_type", sa.String, nullable=False),
        sa.Column("description", sa.String, nullable=False),
        sa.Column("policy_number", sa.String, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("status_detail", sa.String, nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at", TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("completed_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Index("ix_embedding_jobs_owner_id", "owner_id"),
        sa.Index("ix_embedding_jobs_status", "status"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("embedding_jobs")
    op.drop_table("claim_submissions")
    op.drop_table("conversation_messages")
