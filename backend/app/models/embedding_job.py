"""
SQLAlchemy ORM model for the ``embedding_jobs`` table.

Represents an outbox job for async embedding generation. Used to decouple
claim insertion from embedding generation, preventing the claim submission
path from being blocked by external embedding API latency or failures.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EmbeddingJob(Base):
    """Database model for an async embedding generation job.

    Attributes:
        id: Primary key UUID.
        claim_id: The claim identifier this job is for.
        owner_id: UUID of the claim owner.
        claim_type: Type of claim.
        description: Claim description text.
        policy_number: Associated policy number.
        status: Current job status (pending, processing, completed, failed).
        status_detail: Human-readable status or error message.
        retry_count: Number of times this job has been retried.
        created_at: Timestamp of job creation.
        completed_at: Timestamp of job completion (if applicable).
    """

    __tablename__ = "embedding_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    claim_type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    policy_number: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    status_detail: Mapped[str | None] = mapped_column(String, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
