"""
SQLAlchemy ORM model for the ``policy_chunks`` table.

Represents a single chunk of an ingested insurance policy document. Each
chunk is stored with its text content, section metadata, and a computed
``tsvector`` column that supports BM25 full-text search fallback for policy
queries when the primary ChromaDB vector search is unavailable or returns
poor results.
"""

from __future__ import annotations

import uuid
from sqlalchemy import Column, String, Integer, Text, Index
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR

from app.models.base import Base


class PolicyChunk(Base):
    """Database model for a chunk of an ingested policy document.

    Attributes:
        id: Primary key UUID.
        chunk_id: Stable identifier for the chunk, typically derived from
            the source document and chunk index.
        text: The raw text content of the policy chunk.
        section: The policy section this chunk belongs to (e.g.,
            "Section 1: Home Water Damage Coverage").
        source: Source document filename or identifier.
        chunk_index: Zero-based index of this chunk within the document.
        sub_chunk_index: Zero-based index for overlapping chunks within a
            single logical section.
        tsvector: Computed column for PostgreSQL full-text search over the
            chunk text. Used as a BM25 fallback when ChromaDB is unavailable.
    """

    __tablename__ = "policy_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chunk_id = Column(String(128), unique=True, nullable=False, index=True)
    text = Column(Text, nullable=False)
    section = Column(String(255), nullable=False, index=True)
    source = Column(String(255), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    sub_chunk_index = Column(Integer, nullable=False)
    tsvector = Column(TSVECTOR, nullable=False)

    __table_args__ = (
        # GIN index enables fast full-text search over the tsvector column.
        # Critical for the BM25 fallback path in policy_rag.py.
        Index("ix_policy_chunks_tsvector", tsvector, postgresql_using="gin"),
    )
