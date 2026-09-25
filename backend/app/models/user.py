"""
SQLAlchemy ORM model for the ``users`` table.

Represents an authenticated OmniCare user. Password storage uses Argon2id
hashes, which are intentionally stored in a separate column from the username
to avoid accidental leakage in query logs or admin interfaces.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    """Database model for an OmniCare user account.

    Attributes:
        id: Primary key UUID.
        username: Unique, indexed username for authentication.
        password_hash: Argon2id hash of the user's password. Never store
            plaintext passwords.
        created_at: Timestamp of account creation, set automatically by the
            database server.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(300), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
