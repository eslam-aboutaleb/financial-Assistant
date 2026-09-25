"""
REST API package for the OmniCare Financial backend.

Contains versioned API routers. Each version sub-package (e.g. ``v1``)
is responsible for its own domain of endpoints, middleware, and schemas.
"""

from app.api.v1.router import router as api_router

__all__ = ["api_router"]
