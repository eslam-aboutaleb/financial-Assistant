"""
Claims API endpoints for the OmniCare backend.

Provides claim status lookup and the two-step claim submission flow
(prepare -> confirm) to prevent unauthorized claim submissions.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.agent.tools.submit_claim import submit_claim_internal
from app.auth import get_current_user
from app.database import async_session_factory
from app.models.claim_submission import ClaimSubmission
from app.schemas.models import (
    ClaimConfirmationRequest,
    ClaimConfirmationResponse,
    ClaimSubmissionPrepareRequest,
    ClaimSubmissionPrepareResponse,
    ErrorResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/prepare",
    response_model=ClaimSubmissionPrepareResponse,
    status_code=status.HTTP_200_OK,
    summary="Prepare Claim Submission",
    description=(
        "Validates claim data and creates a pending submission record. "
        "Returns a confirmation_token that the frontend must present to the "
        "/confirm endpoint to complete the submission."
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "Pending submission created successfully.",
            "model": ClaimSubmissionPrepareResponse,
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Invalid claim data.",
            "model": ErrorResponse,
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Not authenticated.",
        },
    },
)
async def prepare_claim_submission(
    payload: ClaimSubmissionPrepareRequest,
    current_user_id: str = Depends(get_current_user),
) -> ClaimSubmissionPrepareResponse:
    """Validate claim data and create a pending submission awaiting confirmation.

    This is the first step of the two-step claim submission flow. The agent
    collects the required fields, calls this endpoint to validate them, and
    receives a confirmation_token. The frontend displays a confirmation UI
    and calls /confirm with the token to complete the submission.
    """
    try:
        user_uuid = uuid.UUID(current_user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user",
        ) from None

    # Validate via Pydantic (already done by FastAPI) and prepare claim data
    claim_data = payload.model_dump(mode="json")
    # Serialize Decimal to string for JSONB storage to preserve precision
    # and avoid float rounding issues.
    claim_data["amount"] = str(claim_data["amount"])

    confirmation_token = str(uuid.uuid4())
    expires_at = datetime.now(UTC) + timedelta(minutes=15)

    try:
        async with async_session_factory() as session:
            submission = ClaimSubmission(
                user_id=user_uuid,
                confirmation_token=confirmation_token,
                claim_data=claim_data,
                status="pending",
                expires_at=expires_at,
            )
            session.add(submission)
            await session.commit()
    except SQLAlchemyError as exc:
        logger.exception("Failed to create pending claim submission: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to prepare claim submission. Please try again.",
        ) from exc

    logger.info(
        "Prepared claim submission for user '%s' with token '%s'.",
        current_user_id,
        confirmation_token,
    )

    return ClaimSubmissionPrepareResponse(
        confirmation_token=confirmation_token,
        expires_at=expires_at,
        status="pending",
    )


@router.post(
    "/confirm",
    response_model=ClaimConfirmationResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm Claim Submission",
    description=(
        "Confirms a pending claim submission using the confirmation_token "
        "from the /prepare endpoint. The backend validates the token belongs "
        "to the authenticated user and is not expired before submitting."
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "Claim confirmed and submitted successfully.",
            "model": ClaimConfirmationResponse,
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "Invalid or expired confirmation token.",
            "model": ErrorResponse,
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Not authenticated.",
        },
    },
)
async def confirm_claim_submission(
    payload: ClaimConfirmationRequest,
    current_user_id: str = Depends(get_current_user),
) -> ClaimConfirmationResponse:
    """Confirm and submit a pending claim submission.

    Validates the confirmation token belongs to the authenticated user,
    checks it is not expired, and then calls the internal submit logic.
    """
    try:
        user_uuid = uuid.UUID(current_user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user",
        ) from None

    async with async_session_factory() as session:
        submission = (
            await session.execute(
                select(ClaimSubmission)
                .where(
                    ClaimSubmission.confirmation_token == payload.confirmation_token,
                    ClaimSubmission.user_id == user_uuid,
                    ClaimSubmission.status == "pending",
                )
                .with_for_update()
            )
        ).scalar_one_or_none()

        if submission is None:
            logger.warning(
                "Invalid or expired confirmation token '%s' for user '%s'.",
                payload.confirmation_token,
                current_user_id,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid, expired, or already used confirmation token.",
            )

        if submission.expires_at < datetime.now(UTC):
            submission.status = "expired"
            await session.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Confirmation token has expired.",
            )

        claim_data = submission.claim_data
        result = await submit_claim_internal(
            policy_number=claim_data["policy_number"],
            claim_type=claim_data["claim_type"],
            amount=float(claim_data["amount"]),
            description=claim_data["description"],
            user_uuid=user_uuid,
            session=session,
        )

        if not result.get("success"):
            logger.error(
                "Claim submission failed for token '%s': %s",
                payload.confirmation_token,
                result.get("error", "Unknown error"),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Claim submission failed."),
            )

        submission.status = "completed"
        await session.commit()

    logger.info(
        "Claim confirmed for user '%s': %s",
        current_user_id,
        result.get("message", ""),
    )

    return ClaimConfirmationResponse(
        success=result.get("success", False),
        claim_id=result.get("confirmation_id"),
        status=result.get("status"),
        message=result.get("message", "Claim submission processed."),
    )
