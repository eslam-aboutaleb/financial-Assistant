"""
FastAPI application entry point for OmniCare Financial Backend.

Configures the app with dynamic settings, CORS from environment variables,
lifespan events (RAG ingestion on startup), and mounts the v1 API router.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.router import router as v1_router
from app.config import get_settings
from app.agent.agent import configure_llm
from app.rag.ingest import ingest_policy
from app.schemas.models import ErrorDetail, ErrorResponse
from app.rate_limiter import limiter


# Load centralized settings
settings = get_settings()

# Configure logging using centralized settings
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    On startup:
      - Validates filesystem directories.
      - Ingests the policy document into Chroma vector store (idempotent).
    On shutdown:
      - Gracefully terminates running sessions and resources.
    """
    logger.info(
        "Starting %s (Environment: %s, Version: %s)...",
        settings.app_name,
        settings.environment,
        settings.app_version,
    )


    from app.database import create_all_tables
    try:
        await create_all_tables()
        logger.info("Database tables verified/created.")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")

    # Configure LiteLLM environment variables from centralized settings
    try:
        configure_llm()
        logger.info("LiteLLM configuration applied")
    except Exception as e:
        logger.warning(f"LiteLLM configuration skipped: {e}")

    # Ingest policy documents into vector store on startup
    try:
        count = ingest_policy()
        logger.info(f"Policy ingestion complete: {count} chunks indexed")
    except Exception as e:
        logger.error(f"Policy ingestion failed: {e}")
        # Server continues running so claim status/submission endpoints remain available

    yield  # Server is running and receiving traffic

    logger.info(f"Shutting down {settings.app_name}...")


# Initialize the FastAPI application
app = FastAPI(
    title=settings.app_name,
    description=(
        "Production AI customer assistant API for OmniCare Financial. "
        "Supports grounded policy coverage Q&A (RAG), "
        "claim status lookup, and new claim submission."
    ),
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """
    Convert FastAPI/Pydantic RequestValidationError into a standardized
    ErrorResponse envelope with HTTP 422 Unprocessable Content.

    This ensures the actual response schema matches the OpenAPI declaration
    in the /chat endpoint (responses[422] = ErrorResponse).
    """
    logger.warning(
        "Validation error on %s %s: %s",
        request.method,
        request.url.path,
        exc.errors(),
    )
    error = ErrorDetail(
        code="VALIDATION_ERROR",
        message="Request validation failed. See details for field-level errors.",
        details=exc.errors(),
    )
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(error=error).model_dump(),
    )


# Configure CORS dynamically from validated settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register rate limit exception handler BEFORE middleware so it can catch
# RateLimitExceeded raised by SlowAPIMiddleware.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Register SlowAPIMiddleware so @limiter.limit(...) decorators actually enforce limits.
app.add_middleware(SlowAPIMiddleware)

# Mount API v1 router
app.include_router(v1_router)
