"""
Declarative base class for all SQLAlchemy ORM models in the OmniCare backend.

All model classes (``User``, ``Claim``, ``Conversation``, ``PolicyChunk``)
inherit from this ``Base`` class. SQLAlchemy uses it to track the full set of
mapped entities so that ``Base.metadata.create_all`` can create all tables
at once.

This module should not contain any other logic. Keeping it minimal avoids
circular import issues during application startup.
"""

from sqlalchemy.orm import DeclarativeBase

# The canonical base class for all OmniCare ORM models. Import this in model
# modules rather than importing DeclarativeBase directly, so that the project
# has a single point of control for base class configuration.
class Base(DeclarativeBase):
    pass
