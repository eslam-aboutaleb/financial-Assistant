
from __future__ import annotations
import uuid
from datetime import datetime

"""
Pydantic models for API request/response schemas, error envelopes, and data validation.
"""

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    """Request schema for the /api/v1/chat endpoint."""

    message: str = Field(
        ...,
        description="User's incoming chat message or insurance inquiry",
        examples=["What is covered under water damage?"],
    )

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
    """Schema for tool call information captured during agent reasoning."""

    name: str = Field(..., description="Name of the tool called")
    arguments: dict[str, Any] = Field(
        default_factory=dict, description="Arguments passed to the tool"
    )
    result: dict[str, Any] | None = Field(default=None, description="Result returned by the tool")


class ChatResponse(BaseModel):
    """Response schema for the /api/v1/chat endpoint."""

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


class HealthResponse(BaseModel):
    """Response schema for the /api/v1/health endpoint."""

    status: str = Field(
        default="healthy",
        description="Service health status ('healthy' or 'unhealthy')",
    )


class ErrorDetail(BaseModel):
    """Structured error payload adhering to standardized REST error practices."""

    code: str = Field(..., description="Machine-readable error category code")
    message: str = Field(..., description="Human-readable explanation of the error")
    details: Any | None = Field(
        default=None, description="Additional context or validation failure breakdown"
    )


class ErrorResponse(BaseModel):
    """Standardized top-level API error envelope."""

    error: ErrorDetail = Field(..., description="Error detail container")


class ClaimSubmission(BaseModel):
    """Pydantic model for validating new claim submissions."""

    policy_number: str = Field(
        ...,
        description="Policy number associated with the policyholder (e.g., POL-1092)",
        min_length=1,
    )
    claim_type: Literal["Water Damage", "Personal Property"] = Field(
        ...,
        description="Category/type of insurance claim. Must be exactly 'Water Damage' or 'Personal Property'.",
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

class UserSignup(BaseModel):
    username: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)

class UserSignin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str

class ConversationMetadata(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

class ConversationListResponse(BaseModel):
    conversations: list[ConversationMetadata]

class ConversationDetailResponse(ConversationMetadata):
    messages: list[dict[str, Any]]


# Rebuild models that reference uuid
ConversationListResponse.model_rebuild()
ConversationDetailResponse.model_rebuild()
