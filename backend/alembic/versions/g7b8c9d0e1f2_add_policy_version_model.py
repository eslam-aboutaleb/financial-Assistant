"""add_policy_version_model

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-10-02 14:08:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g7b8c9d0e1f2"
down_revision: str | Sequence[str] | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create policies table
    op.create_table(
        "policies",
        sa.Column(
            "policy_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("product", sa.Text(), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("policy_id"),
    )

    # Create policy_versions table
    op.create_table(
        "policy_versions",
        sa.Column(
            "version_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("policy_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_hash", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.Text(), nullable=True),
        sa.Column("embedding_dim", sa.Text(), nullable=True),
        sa.Column("chunker_version", sa.Text(), nullable=True),
        sa.Column("chunk_size", sa.Text(), nullable=True),
        sa.Column("overlap", sa.Text(), nullable=True),
        sa.Column("retrieval_schema_version", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.policy_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("version_id"),
    )
    op.create_index(
        "ix_policy_versions_policy_effective",
        "policy_versions",
        ["policy_id", "effective_from"],
        unique=False,
    )

    # Add FK columns to policy_chunks
    op.add_column("policy_chunks", sa.Column("policy_id", sa.UUID(), nullable=True))
    op.add_column("policy_chunks", sa.Column("policy_version_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_policy_chunks_policy_id",
        "policy_chunks",
        "policies",
        ["policy_id"],
        ["policy_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_policy_chunks_policy_version_id",
        "policy_chunks",
        "policy_versions",
        ["policy_version_id"],
        ["version_id"],
        ondelete="CASCADE",
    )

    # Backfill existing policy_chunks with a single policy/version row
    op.execute("""
        INSERT INTO policies (policy_id, product, jurisdiction, is_active, created_at, updated_at)
        VALUES (gen_random_uuid(), 'omnicare_base', 'US', true, now(), now())
        RETURNING policy_id
    """)
    op.execute("""
        INSERT INTO policy_versions (policy_id, version, effective_from, source_hash, created_at,
                                     embedding_model, embedding_dim, chunker_version,
                                     chunk_size, overlap, retrieval_schema_version)
        SELECT p.policy_id, 'current', now(), '', now(),
               'text-embedding-3-small', '1536', 'v1',
               '600', '100', 'v1'
        FROM policies p
        WHERE p.product = 'omnicare_base' AND p.jurisdiction = 'US'
        LIMIT 1
        RETURNING version_id
    """)
    op.execute("""
        UPDATE policy_chunks pc
        SET policy_id = p.policy_id,
            policy_version_id = pv.version_id
        FROM policies p
        CROSS JOIN LATERAL (
            SELECT version_id
            FROM policy_versions pv
            WHERE pv.policy_id = p.policy_id
            ORDER BY pv.effective_from DESC
            LIMIT 1
        ) pv
        WHERE p.product = 'omnicare_base' AND p.jurisdiction = 'US'
          AND pc.policy_id IS NULL
    """)

    # Make FK columns non-nullable after backfill
    op.alter_column("policy_chunks", "policy_id", nullable=False)
    op.alter_column("policy_chunks", "policy_version_id", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_policy_chunks_policy_version_id", "policy_chunks", type_="foreignkey")
    op.drop_constraint("fk_policy_chunks_policy_id", "policy_chunks", type_="foreignkey")
    op.drop_column("policy_chunks", "policy_version_id")
    op.drop_column("policy_chunks", "policy_id")
    op.drop_index("ix_policy_versions_policy_effective", table_name="policy_versions")
    op.drop_table("policy_versions")
    op.drop_table("policies")
