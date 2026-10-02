"""merge_policy_and_claim_heads

Revision ID: fc60119aea11
Revises: a1b2c3d4e5f7, 8aef16d71c459439, g7b8c9d0e1f2
Create Date: 2026-10-02 14:35:53.642078

"""
from typing import Sequence, Union



# revision identifiers, used by Alembic.
revision: str = 'fc60119aea11'
down_revision: Union[str, Sequence[str], None] = ('a1b2c3d4e5f7', '8aef16d71c459439', 'g7b8c9d0e1f2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
