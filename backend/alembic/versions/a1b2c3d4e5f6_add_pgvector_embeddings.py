"""add_pgvector_embeddings

Revision ID: a1b2c3d4e5f6
Revises: 6f253a5df2e9
Create Date: 2026-09-26 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '6f253a5df2e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    op.add_column('policy_chunks', sa.Column('embedding', Vector(1536), nullable=True))
    op.create_index('ix_policy_chunks_embedding', 'policy_chunks', ['embedding'], postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_l2_ops'})
    
    op.add_column('claims', sa.Column('embedding', Vector(1536), nullable=True))
    op.add_column('claims', sa.Column('tsvector', postgresql.TSVECTOR(), nullable=True))
    op.create_index('ix_claims_tsvector', 'claims', ['tsvector'], unique=False, postgresql_using='gin')

    # Triggers for tsvector
    op.execute("""
        CREATE OR REPLACE FUNCTION policy_chunks_tsvector_trigger() RETURNS trigger AS $$
        begin
          new.tsvector := to_tsvector('english', coalesce(new.text,''));
          return new;
        end
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER tsvectorupdate BEFORE INSERT OR UPDATE
        ON policy_chunks FOR EACH ROW EXECUTE PROCEDURE policy_chunks_tsvector_trigger();
    """)
    
    op.execute("""
        CREATE OR REPLACE FUNCTION claims_tsvector_trigger() RETURNS trigger AS $$
        begin
          new.tsvector := to_tsvector('english', coalesce(new.description,'') || ' ' || coalesce(new.claim_type,''));
          return new;
        end
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER claims_tsvectorupdate BEFORE INSERT OR UPDATE
        ON claims FOR EACH ROW EXECUTE PROCEDURE claims_tsvector_trigger();
    """)

def downgrade() -> None:
    op.execute("DROP TRIGGER claims_tsvectorupdate ON claims")
    op.execute("DROP FUNCTION claims_tsvector_trigger")
    op.execute("DROP TRIGGER tsvectorupdate ON policy_chunks")
    op.execute("DROP FUNCTION policy_chunks_tsvector_trigger")
    op.drop_index('ix_claims_tsvector', table_name='claims', postgresql_using='gin')
    op.drop_column('claims', 'tsvector')
    op.drop_column('claims', 'embedding')
    op.drop_index('ix_policy_chunks_embedding', table_name='policy_chunks')
    op.drop_column('policy_chunks', 'embedding')
