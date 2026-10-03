"""Convert policy_versions numeric metadata columns from text to integer.

Revision ID: b7c2d4e6f8a0
Revises: fc60119aea11
Create Date: 2026-10-02

`embedding_dim`, `chunk_size` and `overlap` were declared as `Mapped[int | None]` but
mapped to a `Text` column. SQLAlchemy emitted `$n::VARCHAR` for them, so asyncpg rejected
the integer value with "invalid input for query argument $8: 1536 (expected str, got int)"
and every policy ingestion failed at the INSERT into policy_versions. The table has been
empty, so no rows need converting.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c2d4e6f8a0"
down_revision: str | Sequence[str] | None = "fc60119aea11"

_COLUMNS = ("embedding_dim", "chunk_size", "overlap")


def _numeric_using(column: str) -> str:
    """Return a safe text-to-integer conversion expression for ``column``.

    PostgreSQL will not cast text to integer implicitly, so an explicit ``USING`` clause
    is required. It is written to be tolerant of rows that already hold a non-numeric
    value: anything that is not a plain non-negative integer becomes NULL rather than
    aborting the whole migration.
    """
    return f"CASE WHEN {column} ~ '^[0-9]+$' THEN {column}::integer ELSE NULL END"


def upgrade() -> None:
    """Widen the three columns to integer."""
    for column in _COLUMNS:
        op.alter_column(
            "policy_versions",
            column,
            existing_type=sa.Text(),
            type_=sa.Integer(),
            existing_nullable=True,
            postgresql_using=_numeric_using(column),
        )


def downgrade() -> None:
    """Narrow the three columns back to text."""
    for column in _COLUMNS:
        op.alter_column(
            "policy_versions",
            column,
            existing_type=sa.Integer(),
            type_=sa.Text(),
            existing_nullable=True,
            postgresql_using=f"{column}::text",
        )
