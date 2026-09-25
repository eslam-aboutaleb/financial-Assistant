"""
OmniCare Financial Backend Application Package.

This is the root package for the FastAPI backend service. It exposes the
centralized application settings and serves as the namespace root for all
backend sub-packages:

  - ``app.agent``      -- Google ADK agent definition, tools, and prompts.
  - ``app.api``        -- REST API endpoint routers.
  - ``app.rag``        -- Retrieval-Augmented Generation pipeline.
  - ``app.schemas``    -- Pydantic request/response models.
  - ``app.models``     -- SQLAlchemy ORM models.
"""

from app.config import settings

__all__ = ["settings"]
