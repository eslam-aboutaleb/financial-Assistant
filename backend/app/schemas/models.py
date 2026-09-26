"""
Pydantic schemas for the OmniCare Financial backend.

This module defines the request/response envelopes, validation models,
and error payloads used across all API v1 endpoints. Keeping all schemas
in a single module ensures:

  - Consistent validation rules (e.g., claim amounts must be positive).
  - A single source of truth for the OpenAPI contract exposed at /docs.
  - Reusable models between the REST layer and the agent tool layer.

Security-sensitive schemas (``ClaimSubmission``) enforce strict field
constraints to prevent malformed or malicious payloads from reaching
the database.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


# --- Chat Schemas --------------------------------------------------------


class ChatRequest(BaseModel):
    """Request schema for the ``POST /api/v1/chat`` endpoint.

    Attributes:
        user_id: Optional user identifier. If omitted, the authenticated
            user from the bearer token or cookie is used.
        message: The user's incoming chat message or insurance inquiry.
            Limited to 4000 characters to prevent abuse and control token
            costs for LLM processing.
    """

    user_id: str | None = Field(
        default=None,
        description=(
            "Optional user identifier. "
            "If omitted, the authenticated user from the bearer token is used."
        ),
        examples=["usr_123"],
    )
    message: str = Field(
        ...,
        description="User's incoming chat message or insurance inquiry",
        examples=["What is covered under water damage?"],
        max_length=4000,
    )

    @field_validator("user_id")
    @classmethod
    def validate_user_id_format(cls, value: str | None) -> str | None:
        """Normalize the user_id field, treating empty strings as None."""
        if value is None or value == "":
            return None
        value = value.strip()
        if not value:
            return None
        return value

    model_config = ConfigDict(
        str_strip_whitespace=False,
        json_schema_extra={
            "example": {
                "user_id": "usr_123",
                "message": "What is covered under water damage?",
            }
        },
    )


class ToolCallInfo(BaseModel):
    """Schema for tool call information captured during agent reasoning.

    Attributes:
        name: The name of the tool invoked by the agent.
        arguments: The arguments passed to the tool as a dict.
        result: The result returned by the tool, or None if not yet recorded.
    """

    name: str = Field(..., description="Name of the tool called")
    arguments: dict[str, Any] = Field(
        default_factory=dict, description="Arguments passed to the tool"
    )
    result: dict[str, Any] | None = Field(default=None, description="Result returned by the tool")


class ChatResponse(BaseModel):
    """Response schema for the ``POST /api/v1/chat`` endpoint.

    Attributes:
        response: The agent's synthesized text response.
        sources: Document citation sources and policy sections referenced
            in the response.
        tool_calls: List of tools invoked with arguments and execution results,
            providing an auditable trace of the agent's reasoning path.
    """

    response: str = Field(..., description="Agent's synthesized text response")
    sources: list[str] = Field(
        default_factory=list,
        description="Document citation sources and policy sections referenced",
    )
    tool_calls: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of tools invoked with arguments and execution results",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "response": "Water damage caused by sudden pipe bursts is covered up to $25,000.",
                "sources": ["Section 1: Home Water Damage Coverage (sample_policy.md)"],
                "tool_calls": [
                    {
                        "name": "query_policy",
                        "arguments": {"query": "water damage coverage"},
                        "result": {"chunks_found": 1},
                    }
                ],
            }
        }
    )


# --- Health Schema -------------------------------------------------------


class HealthResponse(BaseModel):
    """Response schema for the ``GET /api/v1/health`` endpoint.

    Attributes:
        status: Service health status. Either ``"healthy"`` or ``"unhealthy"``.
    """

    status: str = Field(
        default="healthy",
        description="Service health status ('healthy' or 'unhealthy')",
    )


# --- Error Envelope ------------------------------------------------------


class ErrorDetail(BaseModel):
    """Structured error payload adhering to standardized REST error practices.

    Attributes:
        code: Machine-readable error category code (e.g., ``VALIDATION_ERROR``).
        message: Human-readable explanation of the error suitable for end users.
        details: Additional context or validation failure breakdown, or None.
    """

    code: str = Field(..., description="Machine-readable error category code")
    message: str = Field(..., description="Human-readable explanation of the error")
    details: Any | None = Field(
        default=None, description="Additional context or validation failure breakdown"
    )


class ErrorResponse(BaseModel):
    """Standardized top-level API error envelope.

    All error responses from the API follow this shape:
    ``{"error": {"code": "...", "message": "...", "details": ...}}``
    """

    error: ErrorDetail = Field(..., description="Error detail container")


# --- Claim Submission Schema ---------------------------------------------


class ClaimSubmission(BaseModel):
    """Pydantic model for validating new claim submissions.

    All fields are required and validated before any database write occurs.
    This prevents malformed or malicious payloads from reaching the
    persistence layer.

    Attributes:
        policy_number: The policyholder's policy number.
        claim_type: Category/type of insurance claim.
        amount: Total claim amount in US dollars. Must be greater than 0.
        description: Detailed factual description of the incident or claim
            event. Must be at least 10 characters to ensure sufficient
            detail for claims processing.
    """

    policy_number: str = Field(
        ...,
        description="Policy number associated with the policyholder (e.g., POL-1092)",
        min_length=1,
    )
    claim_type: str = Field(
        ...,
        description="Category/type of insurance claim (e.g., Water Damage, Personal Property)",
        min_length=1,
    )
    amount: float = Field(
        ...,
        description="Total claim amount in US dollars (must be greater than 0)",
        gt=0,
    )
    description: str = Field(
        ...,
        description="Detailed factual description of the incident or claim event",
        min_length=10,
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "policy_number": "POL-1092",
                "claim_type": "Water Damage",
                "amount": 2500.0,
                "description": "Sudden frozen pipe burst in master bathroom causing floor flooding",
            }
        },
    )


# --- Authentication Schemas ----------------------------------------------


class UserSignup(BaseModel):
    """Request schema for user registration.

    Attributes:
        username: Desired username. Must be at least 3 characters.
        password: Account password. Must be at least 6 characters.
    """

    username: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)


class UserSignin(BaseModel):
    """Request schema for user authentication.

    Attributes:
        username: The user's registered username.
        password: The user's plaintext password for verification.
    """

    username: str
    password: str


class Token(BaseModel):
    """Response schema for authentication endpoints (signup/signin).

    Attributes:
        access_token: The signed JWT access token.
        token_type: The token type (always ``"bearer"``).
        user_id: The authenticated user's UUID as a string.
    """

    access_token: str
    token_type: str
    user_id: str


# --- Conversation Schemas ------------------------------------------------


class ConversationMetadata(BaseModel):
    """Lightweight metadata for a conversation, used in sidebar lists.

    Attributes:
        id: The conversation's primary key UUID.
        title: Human-readable conversation title.
        created_at: Timestamp of conversation creation.
        updated_at: Timestamp of the last message or metadata update.
    """

    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    """Response schema for listing a user's conversations.

    Attributes:
        conversations: Ordered list of conversation metadata objects.
    """

    conversations: list[ConversationMetadata]


class ConversationDetailResponse(ConversationMetadata):
    """Response schema for fetching a single conversation with full message history.

    Attributes:
        messages: Full list of message objects from the conversation history.
            Each message contains at least ``id``, ``role``, ``content``, and
            ``timestamp``, plus optional ``sources`` and ``tool_calls`` fields.
    """

    messages: list[dict[str, Any]]


# Rebuild models that reference uuid to resolve forward references.
ConversationListResponse.model_rebuild()
ConversationDetailResponse.model_rebuild()
