"""
SQLAlchemy ORM model for the ``policy_chunks`` table.

Represents a single chunk of an ingested insurance policy document. Each
chunk is stored with its text content, section metadata, a computed
``tsvector`` column for BM25 full-text search, and a ``embedding`` column
for pgvector hybrid retrieval.
"""

from __future__ import annotations

import uuid
from sqlalchemy import Column, String, Integer, Text, Index
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from pgvector.sqlalchemy import Vector

from app.models.base import Base


class PolicyChunk(Base):
    """Database model for a chunk of an ingested policy document."""

    __tablename__ = "policy_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chunk_id = Column(String(128), unique=True, nullable=False, index=True)
    text = Column(Text, nullable=False)
    section = Column(String(255), nullable=False, index=True)
    source = Column(String(255), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    sub_chunk_index = Column(Integer, nullable=False)
    tsvector = Column(TSVECTOR, nullable=True)
    embedding = Column(Vector(1536), nullable=False)

    __table_args__ = (
        Index("ix_policy_chunks_tsvector", tsvector, postgresql_using="gin"),
        Index(
            "ix_policy_chunks_embedding",
            embedding,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_l2_ops"},
        ),
    )
