"""
SQLAlchemy ORM model for the ``claims`` table.

Represents an insurance claim filed by an OmniCare policyholder. Each claim
is linked to its owner via a foreign key, stores structured claim metadata,
and includes a computed ``tsvector`` column for BM25 full-text search and a
``embedding`` column for pgvector hybrid retrieval.
"""

import uuid
from sqlalchemy import String, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from pgvector.sqlalchemy import Vector
from sqlalchemy import Index

from app.models.base import Base


class Claim(Base):
    """Database model for an OmniCare insurance claim.

    Attributes:
        id: Primary key UUID.
        claim_id: Human-readable claim identifier (e.g., "CLM-8821").
        policy_number: The policyholder's policy number, indexed for lookup.
        claim_type: Category of the claim (e.g., "Water Damage", "Personal Property").
        status: Current processing status (e.g., "Submitted", "Approved", "Denied").
        amount: Claimed amount in US dollars.
        description: Factual description of the incident.
        owner_id: Foreign key to the user who filed the claim.
        embedding: pgvector embedding of the claim text for hybrid search.
        tsvector: PostgreSQL tsvector for BM25 full-text search over the description.
    """

    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    policy_number: Mapped[str] = mapped_column(String, index=True)
    claim_type: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    amount: Mapped[float] = mapped_column(Float)
    description: Mapped[str] = mapped_column(String)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    embedding: Mapped[str] = mapped_column(Vector(1536), nullable=False, server_default="[0]")
    tsvector: Mapped[str] = mapped_column(TSVECTOR, nullable=False, server_default="''")

    __table_args__ = (Index("ix_claims_tsvector", tsvector, postgresql_using="gin"),)
