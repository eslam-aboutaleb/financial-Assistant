"""
Pydantic schemas package for the OmniCare Financial backend.

Exports all request/response models, validation schemas, and error envelopes
used by the API v1 endpoints. These schemas define the OpenAPI contract
and enforce runtime data validation.
"""

from app.schemas.models import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    ErrorDetail,
    ErrorResponse,
    ClaimSubmission,
    UserSignup,
    UserSignin,
    Token,
    ConversationMetadata,
    ConversationListResponse,
    ConversationDetailResponse,
)

__all__ = [
    "ChatRequest",
    "ChatResponse",
    "HealthResponse",
    "ErrorDetail",
    "ErrorResponse",
    "ClaimSubmission",
    "UserSignup",
    "UserSignin",
    "Token",
    "ConversationMetadata",
    "ConversationListResponse",
    "ConversationDetailResponse",
]
