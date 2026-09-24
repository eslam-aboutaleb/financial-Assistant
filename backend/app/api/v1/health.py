"""
Health check endpoint.
GET /api/v1/health - Evaluates and returns service operational status.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Response, status

from app.config import settings
from app.schemas.models import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Service Health Check",
    description=(
        "Returns the operational health status of the OmniCare backend API "
        "and critical dependencies."
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "Service is fully operational and healthy.",
            "model": HealthResponse,
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Service or dependent datastore is degraded or unavailable.",
            "model": HealthResponse,
        },
    },
)
async def health_check(response: Response) -> HealthResponse:
    """
    Evaluates backend system health and dependency availability.

    Verifies:
    1. Core API server execution.
    2. Accessibility of filesystem datastores (claims file directory).

    Returns:
        HealthResponse indicating 'healthy' (HTTP 200) or 'unhealthy' (HTTP 503).
    """
    # Verify claims storage accessibility
    try:
        claims_path = Path(settings.claims_file_path)
        claims_parent = claims_path.parent
        if not claims_parent.exists():
            claims_parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"Health check dependency failure: {e}")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="unhealthy")

    return HealthResponse(status="healthy")
