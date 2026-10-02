"""
Comprehensive coverage tests for uncovered backend paths.

This module supplements existing tests to push backend coverage toward 100%
by exercising error paths, edge cases, and exception handlers that are
missed by the current test suite.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEST_USER_ID = "00000000-0000-0000-0000-000000000001"


def _override_get_current_user():
    from app.auth import get_current_user
    from app.main import app

    async def _override():
        return _TEST_USER_ID

    app.dependency_overrides[get_current_user] = _override
    return {"Authorization": f"Bearer test-token-for-{_TEST_USER_ID}"}


def _clear_auth_override():
    from app.auth import get_current_user
    from app.main import app

    app.dependency_overrides.pop(get_current_user, None)


# ===========================================================================
# app.agent.agent
# ===========================================================================


class TestAgentSessionEviction:
    """Cover session eviction and exception handling in agent.py."""

    @pytest.mark.asyncio
    async def test_ensure_session_evicts_oldest_when_at_capacity(self):
        from app.agent.agent import _MAX_SESSIONS, _user_sessions, _ensure_session

        _user_sessions.clear()
        for i in range(_MAX_SESSIONS):
            uid = f"user-{i}"
            _user_sessions[uid] = f"session-{i}"

        new_user = f"user-new-{uuid.uuid4().hex[:8]}"
        with patch("app.agent.agent.session_service") as mock_session_service:
            mock_session_service.create_session = AsyncMock()
            mock_session_service.delete_session = AsyncMock()
            session_id = await _ensure_session(new_user)
            assert session_id is not None
            assert len(_user_sessions) == _MAX_SESSIONS
            oldest = next(iter(_user_sessions))
            assert oldest != new_user

    @pytest.mark.asyncio
    async def test_ensure_session_delete_session_exception_logged(self):
        from app.agent.agent import _user_sessions, _ensure_session

        _user_sessions.clear()
        _user_sessions["evict-user"] = "session-evict"
        # Force eviction by filling to capacity then adding one more
        for i in range(500):
            _user_sessions[f"user-{i}"] = f"session-{i}"
        _user_sessions["evict-user"] = "session-evict"
        with patch("app.agent.agent.session_service") as mock_session_service:
            mock_session_service.create_session = AsyncMock()
            mock_session_service.delete_session = AsyncMock(
                side_effect=Exception("delete failed")
            )
            with patch("app.agent.agent.logger") as mock_logger:
                await _ensure_session("new-user-after-capacity")
                mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_reset_user_session_delete_exception_logged(self):
        from app.agent.agent import _user_sessions, reset_user_session

        _user_sessions["reset-user"] = "session-reset"
        with patch("app.agent.agent.session_service") as mock_session_service:
            mock_session_service.delete_session = AsyncMock(
                side_effect=Exception("delete failed")
            )
            with patch("app.agent.agent.logger") as mock_logger:
                await reset_user_session("reset-user")
                mock_logger.warning.assert_called()
        assert "reset-user" not in _user_sessions

    @pytest.mark.asyncio
    async def test_run_agent_stream_populates_result(self):
        from app.agent.agent import run_agent_stream

        user_id = str(uuid.uuid4())
        mock_event = MagicMock()
        mock_event.is_final_response.return_value = True
        mock_event.content.parts = [MagicMock(text="streamed text")]
        mock_event.model_dump_json.return_value = '{"text": "streamed text"}'

        async def mock_run_async(**kwargs):
            yield mock_event

        mock_runner = MagicMock()
        mock_runner.run_async = mock_run_async

        with patch("app.agent.agent.runner", mock_runner):
            with patch("app.agent.agent.session_service") as mock_session_service:
                mock_session_service.create_session = AsyncMock()
                mock_session_service.delete_session = AsyncMock()
                result = MagicMock()
                chunks = []
                async for chunk in run_agent_stream(
                    user_id=user_id, message="test", result=result
                ):
                    chunks.append(chunk)

        assert result.session_id is not None
        assert result.final_text_parts == ["streamed text"]
        assert result.tool_calls == []
        assert result.sources == []

    @pytest.mark.asyncio
    async def test_run_agent_stream_collects_tool_calls_and_sources(self):
        from app.agent.agent import run_agent_stream

        user_id = str(uuid.uuid4())
        mock_fc = MagicMock()
        mock_fc.name = "query_policy"
        mock_fc.args = {"query": "test"}

        mock_fr = MagicMock()
        mock_fr.name = "query_policy"
        mock_fr.response = {
            "sources": [{"section": "Section 1", "source": "policy.md"}],
            "citation": "Claim CLM-123 in system",
        }

        mock_event_fc = MagicMock()
        mock_event_fc.get_function_calls.return_value = [mock_fc]
        mock_event_fc.get_function_responses.return_value = None
        mock_event_fc.is_final_response.return_value = False
        mock_event_fc.content = None
        mock_event_fc.model_dump_json.return_value = '{"fc": true}'

        mock_event_fr = MagicMock()
        mock_event_fr.get_function_calls.return_value = None
        mock_event_fr.get_function_responses.return_value = [mock_fr]
        mock_event_fr.is_final_response.return_value = True
        mock_event_fr.content.parts = [MagicMock(text="done")]
        mock_event_fr.model_dump_json.return_value = '{"fr": true}'

        async def mock_run_async(**kwargs):
            yield mock_event_fc
            yield mock_event_fr

        mock_runner = MagicMock()
        mock_runner.run_async = mock_run_async

        with patch("app.agent.agent.runner", mock_runner):
            with patch("app.agent.agent.session_service") as mock_session_service:
                mock_session_service.create_session = AsyncMock()
                mock_session_service.delete_session = AsyncMock()
                result = MagicMock()
                async for _ in run_agent_stream(
                    user_id=user_id, message="test", result=result
                ):
                    pass

        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "query_policy"
        assert len(result.sources) == 2
        assert result.tool_calls[0].get("result") == mock_fr.response


# ===========================================================================
# app.agent.tools.claim_status
# ===========================================================================


class TestClaimStatusTool:
    """Cover error paths in claim_status.py."""

    @pytest.mark.asyncio
    async def test_get_claim_status_returns_unauthorized_when_no_context(self):
        from app.agent.tools.claim_status import get_claim_status

        with patch("app.agent.tools.claim_status.current_user_id") as mock_cv:
            mock_cv.get.side_effect = LookupError
            result = await get_claim_status(claim_id="CLM-9999")
            assert result["found"] is False
            assert "Unauthorized" in result["error"]

    @pytest.mark.asyncio
    async def test_get_claim_status_returns_error_on_exception(self):
        from app.agent.tools.claim_status import get_claim_status

        with patch("app.agent.tools.claim_status.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__.side_effect = Exception("DB down")
            with patch("app.agent.tools.claim_status.current_user_id") as mock_cv:
                mock_cv.get.return_value = uuid.UUID(_TEST_USER_ID)
                result = await get_claim_status(claim_id="CLM-9999")
                assert result["found"] is False
                assert "Unable to retrieve" in result["error"]


# ===========================================================================
# app.agent.tools.submit_claim
# ===========================================================================


class TestSubmitClaimTool:
    """Cover error paths in submit_claim.py."""

    @pytest.mark.asyncio
    async def test_prepare_claim_submission_returns_error_on_exception(self):
        from app.agent.context import current_user_id
        from app.agent.tools.submit_claim import prepare_claim_submission

        current_user_id.set(uuid.uuid4())
        with patch("app.agent.tools.submit_claim.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__.side_effect = Exception("DB down")
            result = await prepare_claim_submission(
                policy_number="POL-1092",
                claim_type="Water Damage",
                amount=2500.0,
                description="Frozen pipe burst causing water damage to hardwood floors",
            )
            assert result.get("success") is False
            assert "could not be prepared" in result["error"]

    @pytest.mark.asyncio
    async def test_submit_claim_internal_validation_error(self):
        from app.agent.tools.submit_claim import submit_claim_internal

        result = await submit_claim_internal(
            policy_number="POL-1092",
            claim_type="Water Damage",
            amount=-5.0,
            description="short",
            user_uuid=uuid.UUID(_TEST_USER_ID),
        )
        assert result.get("success") is False
        assert "validation_errors" in result


# ===========================================================================
# app.api.v1.auth
# ===========================================================================


class TestAuthAPI:
    """Cover uncovered auth API paths."""

    def test_signup_duplicate_username_returns_409(self, test_client):
        username = f"dupuser_{uuid.uuid4().hex[:8]}"
        payload = {"username": username, "password": "TestPass123!"}
        r1 = test_client.post("/api/v1/auth/signup", json=payload)
        assert r1.status_code == 201
        r2 = test_client.post("/api/v1/auth/signup", json=payload)
        assert r2.status_code == 409

    def test_signup_integrity_error_returns_409(self, test_client):
        username = f"intuser_{uuid.uuid4().hex[:8]}"
        payload = {"username": username, "password": "TestPass123!"}
        test_client.post("/api/v1/auth/signup", json=payload)
        with patch(
            "app.api.v1.auth.run_in_threadpool",
            side_effect=IntegrityError("duplicate", None, None),
        ):
            pass

    def test_signin_uses_dummy_hash_for_nonexistent_user(self, test_client):
        response = test_client.post(
            "/api/v1/auth/signin",
            json={"username": f"nonexistent_{uuid.uuid4().hex}", "password": "AnyPass123!"},
        )
        assert response.status_code == 401

    def test_get_current_user_info_returns_user_id(self, test_client, mock_current_user):
        response = test_client.get("/api/v1/auth/me", headers=mock_current_user)
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == _TEST_USER_ID


# ===========================================================================
# app.api.v1.chat
# ===========================================================================


class TestChatAPI:
    """Cover uncovered chat endpoint paths."""

    def test_chat_bad_request_error_tool_call_id_retry(self, test_client, mock_current_user):
        import litellm

        with patch("app.api.v1.chat.run_agent", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                litellm.BadRequestError(
                    message="tool_call_id mismatch",
                    model="gpt-4o-mini",
                    llm_provider="openai",
                ),
                {"response": "retry ok", "sources": [], "tool_calls": []},
            ]
            with patch("app.api.v1.chat.reset_user_session", new_callable=AsyncMock):
                response = test_client.post(
                    "/api/v1/chat",
                    json={"message": "retry me"},
                    headers=mock_current_user,
                )
                assert response.status_code == 200

    def test_chat_http_exception_re_raised(self, test_client, mock_current_user):
        from fastapi import HTTPException

        with patch("app.api.v1.chat.run_agent", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = HTTPException(status_code=400, detail="bad")
            response = test_client.post(
                "/api/v1/chat",
                json={"message": "hello"},
                headers=mock_current_user,
            )
            assert response.status_code == 400

    def test_chat_reset_endpoint(self, test_client, mock_current_user):
        with patch("app.api.v1.chat.reset_user_session", new_callable=AsyncMock):
            response = test_client.post(
                "/api/v1/chat/reset", headers=mock_current_user
            )
            assert response.status_code == 204


# ===========================================================================
# app.api.v1.chat_stream
# ===========================================================================


class TestChatStreamAPI:
    """Cover uncovered chat_stream paths."""

    def test_transform_adk_event_invalid_json_fallback(self):
        from app.api.v1.chat_stream import _transform_adk_event

        result = _transform_adk_event("not-valid-json")
        assert result.startswith("data:")

    def test_transform_adk_event_final_response_with_sources(self):
        from app.api.v1.chat_stream import _transform_adk_event

        event = {"is_final_response": True}
        event_json = json.dumps(event)
        sources = [{"section": "Section 1", "source": "policy.md"}]
        result = _transform_adk_event(event_json, sources=sources)
        assert "response_complete" in result
        assert "Section 1" in result

    def test_transform_adk_event_raw_passthrough(self):
        from app.api.v1.chat_stream import _transform_adk_event

        raw = '{"type": "other", "data": "raw"}'
        result = _transform_adk_event(raw)
        assert result == f"data: {raw}\n\n"

    def test_chat_stream_client_disconnect(self, test_client, mock_current_user):
        async def mock_run(*args, **kwargs):
            yield 'data: {"type": "text_delta", "content": "Hello"}\n\n'

        with patch("app.api.v1.chat_stream.run_agent_stream") as mock_run_agent_stream:
            mock_run_agent_stream.return_value = mock_run()
            with patch(
                "app.api.v1.chat_stream.event_generator"
            ) as mock_gen:
                async def _gen():
                    yield 'data: {"type": "text_delta", "content": "Hello"}\n\n'
                mock_gen.return_value = _gen()
                response = test_client.post(
                    "/api/v1/chat/stream",
                    json={"message": "Hi"},
                    headers=mock_current_user,
                )
                assert response.status_code == 200

    def test_chat_stream_value_error_context_suppressed(self, test_client, mock_current_user):
        async def mock_run(*args, **kwargs):
            yield 'data: {"type": "text_delta", "content": "Hello"}\n\n'
            raise ValueError("was created in a different Context")

        with patch("app.api.v1.chat_stream.run_agent_stream") as mock_run_agent_stream:
            mock_run_agent_stream.return_value = mock_run()
            response = test_client.post(
                "/api/v1/chat/stream",
                json={"message": "Hi"},
                headers=mock_current_user,
            )
            assert response.status_code == 200
            assert "response_complete" in response.text

    def test_persist_streamed_turn_logs_error(self):
        from app.api.v1.chat_stream import _persist_streamed_turn

        with patch("app.api.v1.chat_stream.save_conversation_turn", new_callable=AsyncMock) as mock_save:
            mock_save.side_effect = Exception("DB error")
            with patch("app.api.v1.chat_stream.logger") as mock_logger:
                asyncio.run(
                    _persist_streamed_turn(
                        user_id=_TEST_USER_ID,
                        session_id="session-1",
                        message="hello",
                        result=MagicMock(final_text_parts=["hello"], sources=[], tool_calls=[]),
                    )
                )
                mock_logger.error.assert_called()


# ===========================================================================
# app.api.v1.claims
# ===========================================================================


class TestClaimsAPI:
    """Cover uncovered claims endpoint paths."""

    def test_prepare_claim_invalid_user_returns_401(self, test_client, mock_current_user):
        with patch("app.api.v1.claims.uuid.UUID", side_effect=ValueError("bad uuid")):
            response = test_client.post(
                "/api/v1/claims/prepare",
                json={
                    "policy_number": "POL-1092",
                    "claim_type": "Water Damage",
                    "amount": 2500.0,
                    "description": "Frozen pipe burst causing water damage to hardwood floors",
                },
                headers=mock_current_user,
            )
        assert response.status_code == 401

    def test_prepare_claim_sqlalchemy_error_returns_500(self, test_client, mock_current_user):
        with patch("app.api.v1.claims.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_session.add = MagicMock()
            mock_session.commit = AsyncMock(side_effect=Exception("DB error"))
            mock_factory.return_value.__aenter__.return_value = mock_session
            response = test_client.post(
                "/api/v1/claims/prepare",
                json={
                    "policy_number": "POL-1092",
                    "claim_type": "Water Damage",
                    "amount": 2500.0,
                    "description": "Frozen pipe burst causing water damage to hardwood floors",
                },
                headers=mock_current_user,
            )
        assert response.status_code == 500

    def test_confirm_claim_invalid_user_returns_401(self, test_client):
        from app.auth import get_current_user
        from app.main import app

        async def _bad_user():
            return "not-a-valid-uuid"

        app.dependency_overrides[get_current_user] = _bad_user
        try:
            response = test_client.post(
                "/api/v1/claims/confirm",
                json={"confirmation_token": str(uuid.uuid4())},
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 401

    def test_confirm_claim_submission_none_returns_400(self, test_client, mock_current_user):
        with patch("app.api.v1.claims.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result
            mock_factory.return_value.__aenter__.return_value = mock_session
            response = test_client.post(
                "/api/v1/claims/confirm",
                json={"confirmation_token": str(uuid.uuid4())},
                headers=mock_current_user,
            )
        assert response.status_code == 400

    def test_confirm_claim_expired_token_returns_400(self, test_client, mock_current_user):
        token = str(uuid.uuid4())
        user_uuid = uuid.UUID(_TEST_USER_ID)
        past_expiry = datetime.now(UTC) - timedelta(minutes=5)

        mock_submission = MagicMock()
        mock_submission.confirmation_token = token
        mock_submission.user_id = user_uuid
        mock_submission.status = "pending"
        mock_submission.expires_at = past_expiry
        mock_submission.claim_data = {
            "policy_number": "POL-1092",
            "claim_type": "Water Damage",
            "amount": "2500.00",
            "description": "Frozen pipe burst causing water damage to hardwood floors",
        }

        with patch("app.api.v1.claims.async_session_factory") as mock_factory:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_submission
            mock_session.execute.return_value = mock_result
            mock_factory.return_value.__aenter__.return_value = mock_session
            response = test_client.post(
                "/api/v1/claims/confirm",
                json={"confirmation_token": token},
                headers=mock_current_user,
            )
        assert response.status_code == 400
        assert "expired" in response.json()["error"]["message"].lower()


# ===========================================================================
# app.api.v1.health
# ===========================================================================


class TestHealthAPI:
    """Cover health endpoint db failure path."""

    def test_health_check_db_failure(self, test_client):
        from unittest.mock import AsyncMock as AMock

        async def _failing_check():
            raise Exception("DB down")

        with patch("app.api.v1.health.asyncio.wait_for", side_effect=Exception("DB down")):
            response = test_client.get("/api/v1/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"


# ===========================================================================
# app.api.v1.rag_eval
# ===========================================================================


class TestRagEvalAPI:
    """Cover uncovered rag_eval paths."""

    def test_evaluate_rag_invalid_category_returns_422(self, test_client, mock_current_user):
        response = test_client.post(
            "/api/v1/rag/evaluate",
            json={"mode": "retrieval-only", "judge": "heuristic", "category": "invalid"},
            headers=mock_current_user,
        )
        assert response.status_code == 422

    def test_evaluate_rag_invalid_difficulty_returns_422(self, test_client, mock_current_user):
        response = test_client.post(
            "/api/v1/rag/evaluate",
            json={"mode": "retrieval-only", "judge": "heuristic", "difficulty": "invalid"},
            headers=mock_current_user,
        )
        assert response.status_code == 422

    def test_list_eval_dataset_invalid_category_returns_422(self, test_client, mock_current_user):
        response = test_client.get(
            "/api/v1/rag/dataset?category=invalid", headers=mock_current_user
        )
        assert response.status_code == 422

    def test_list_eval_dataset_invalid_difficulty_returns_422(self, test_client, mock_current_user):
        response = test_client.get(
            "/api/v1/rag/dataset?difficulty=invalid", headers=mock_current_user
        )
        assert response.status_code == 422


# ===========================================================================
# app.auth
# ===========================================================================


class TestAuthModule:
    """Cover uncovered auth module paths."""

    def test_decode_token_malformed_subject_raises_invalid_token(self):
        from app.auth import _InvalidTokenError, _decode_token

        token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.bad"
        with pytest.raises(_InvalidTokenError):
            _decode_token(token)

    def test_get_current_user_clears_cookie_for_nonexistent_user(self, test_client):
        from app.auth import _InvalidTokenError

        with patch("app.auth._decode_token", side_effect=_InvalidTokenError("expired")):
            response = test_client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer invalid-token"},
            )
        assert response.status_code == 401


# ===========================================================================
# app.config
# ===========================================================================


class TestConfig:
    """Cover uncovered config paths."""

    def test_cors_origins_comma_separated_string(self):
        from app.config import Settings

        settings = Settings(cors_origins="http://a.com, http://b.com")
        assert "http://a.com" in settings.cors_origins
        assert "http://b.com" in settings.cors_origins

    def test_cors_origins_json_array_string(self):
        from app.config import Settings

        settings = Settings(cors_origins='["http://a.com", "http://b.com"]')
        assert "http://a.com" in settings.cors_origins
        assert "http://b.com" in settings.cors_origins

    def test_cors_origins_wildcard_rejected(self):
        from app.config import Settings

        with pytest.raises(ValueError, match="Wildcard origin"):
            Settings(cors_origins=["*"])

    def test_cors_origins_list_tuple_accepted(self):
        from app.config import Settings

        settings = Settings(cors_origins=["http://a.com", "http://b.com"])
        assert "http://a.com" in settings.cors_origins


# ===========================================================================
# app.main
# ===========================================================================


class TestMain:
    """Cover uncovered main.py paths."""

    def test_run_alembic_migrations_failure_raises(self):
        from app.main import _run_alembic_migrations

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stderr = "migration failed"
            with pytest.raises(RuntimeError, match="Database migration failed"):
                asyncio.run(_run_alembic_migrations())

    def test_run_alembic_migrations_exception_raises(self):
        from app.main import _run_alembic_migrations

        with patch("subprocess.run", side_effect=Exception("subprocess error")):
            with pytest.raises(RuntimeError, match="Failed to run database migrations"):
                asyncio.run(_run_alembic_migrations())

    def test_lifespan_configure_llm_failure_continues(self):
        from app.main import lifespan

        app = MagicMock()
        with patch("app.main.configure_llm", side_effect=Exception("LLM config failed")):
            with patch("app.main.ingest_policy", new_callable=AsyncMock):
                with patch("app.main._run_alembic_migrations"):
                    gen = lifespan(app)
                    asyncio.run(gen.__aenter__())
                    asyncio.run(gen.__aexit__(None, None, None))


# ===========================================================================
# app.middleware
# ===========================================================================


class TestMiddleware:
    """Cover uncovered middleware paths."""

    def test_request_size_limit_content_length_value_error(self):
        from app.middleware import RequestSizeLimitMiddleware

        middleware = RequestSizeLimitMiddleware(MagicMock(), max_upload_size=1024)
        request = MagicMock()
        request.headers.get.return_value = "not-a-number"
        request.body = AsyncMock(return_value=b"")

        async def call_next(req):
            return MagicMock()

        response = asyncio.run(middleware.dispatch(request, call_next))
        assert response.status_code == 200

    def test_request_size_limit_no_content_length_exceeds(self):
        from app.middleware import RequestSizeLimitMiddleware

        middleware = RequestSizeLimitMiddleware(MagicMock(), max_upload_size=10)
        request = MagicMock()
        request.headers.get.return_value = None
        request.body = AsyncMock(return_value=b"a" * 20)
        response = asyncio.run(middleware.dispatch(request, MagicMock()))
        assert response.status_code == 413

    def test_request_size_limit_exceeded_returns_413(self):
        from app.middleware import RequestSizeLimitMiddleware

        middleware = RequestSizeLimitMiddleware(MagicMock(), max_upload_size=10)
        request = MagicMock()
        request.headers.get.return_value = "999"
        request.body = AsyncMock(return_value=b"small")
        response = asyncio.run(middleware.dispatch(request, MagicMock()))
        assert response.status_code == 413
        data = json.loads(response.body)
        assert data["error"]["code"] == "PAYLOAD_TOO_LARGE"


# ===========================================================================
# app.rag.answer_evaluator
# ===========================================================================


class TestAnswerEvaluator:
    """Cover uncovered answer_evaluator paths."""

    def test_key_fact_recall_no_key_facts_falls_back_to_overlap(self):
        from app.rag.answer_evaluator import _key_fact_recall

        result = _key_fact_recall("some answer", "no amounts or numbers here")
        assert 0.0 <= result <= 1.0

    def test_evaluate_answer_heuristic_faithfulness_fallback(self):
        from app.rag.answer_evaluator import evaluate_answer_heuristic

        score = evaluate_answer_heuristic(
            query="test",
            answer="some answer",
            gold_answer="gold answer",
            retrieved_context="",
        )
        assert score.faithfulness >= 0.0

    def test_evaluate_answer_heuristic_conciseness_very_verbose(self):
        from app.rag.answer_evaluator import evaluate_answer_heuristic

        long_answer = "word " * 1000
        score = evaluate_answer_heuristic(
            query="test",
            answer=long_answer,
            gold_answer="short answer",
            retrieved_context="",
        )
        assert score.conciseness == 0.2

    def test_evaluate_answer_heuristic_empty_answer(self):
        from app.rag.answer_evaluator import evaluate_answer_heuristic

        score = evaluate_answer_heuristic(
            query="test", answer="", gold_answer="gold", retrieved_context=""
        )
        assert score.reasoning == "Empty answer"


# ===========================================================================
# app.rag.embedding_jobs
# ===========================================================================


class TestEmbeddingJobs:
    """Cover uncovered embedding_jobs paths."""

    @pytest.mark.asyncio
    async def test_enqueue_embedding_job_exception_logged(self):
        from app.rag.embedding_jobs import enqueue_embedding_job

        with patch("app.rag.embedding_jobs.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__.side_effect = Exception("DB down")
            with patch("app.rag.embedding_jobs.logger") as mock_logger:
                await enqueue_embedding_job(
                    claim_uuid=uuid.UUID(_TEST_USER_ID),
                    claim_id="CLM-9999",
                    owner_id=uuid.UUID(_TEST_USER_ID),
                    claim_type="Water Damage",
                    description="Test",
                    policy_number="POL-1092",
                    claim_status="Submitted",
                )
                mock_logger.exception.assert_called()


# ===========================================================================
# app.rag.eval_runner
# ===========================================================================


class TestEvalRunner:
    """Cover uncovered eval_runner paths."""

    @pytest.mark.asyncio
    async def test_run_retrieval_eval_exception_in_sample(self):
        from app.rag.eval_runner import _run_retrieval_eval

        with patch(
            "app.rag.eval_runner.retrieve_hybrid",
            side_effect=Exception("search failed"),
        ):
            metrics, per_sample = await _run_retrieval_eval(
                dataset=[MagicMock(query="test", expected_sections=["Section 1"])],
                n_results=5,
            )
        assert metrics.errors == 1
        assert per_sample[0].get("error") is not None

    @pytest.mark.asyncio
    async def test_run_answer_eval_no_generated_answer(self):
        from app.rag.answer_evaluator import AnswerScore, evaluate_answer_heuristic
        from app.rag.eval_runner import _run_answer_eval

        sample = MagicMock(query="test", gold_answer="gold answer")
        per_sample = [{"context": "", "chunks_found": 0}]
        with patch(
            "app.rag.eval_runner.evaluate_answer_heuristic",
            wraps=evaluate_answer_heuristic,
        ):
            metrics, details = await _run_answer_eval(
                dataset=[sample],
                per_sample_retrieval=per_sample,
                judge="heuristic",
            )
        assert metrics.errors == 0

    @pytest.mark.asyncio
    async def test_run_evaluation_no_dataset_returns_early(self):
        from app.rag.eval_runner import run_evaluation

        with patch("app.rag.eval_runner.get_eval_dataset", return_value=[]):
            result = await run_evaluation()
        assert result.summary == "No evaluation samples matched the filters."

    @pytest.mark.asyncio
    async def test_run_evaluation_retrieval_only_mode(self):
        from dataclasses import dataclass

        from app.rag.eval_runner import EvalConfig, run_evaluation

        @dataclass
        class FakeMetrics:
            recall_at_k: float = 1.0
            precision_at_k: float = 1.0
            mrr: float = 1.0
            avg_latency_ms: float = 10.0
            total_queries: int = 1
            errors: int = 0

        with patch("app.rag.eval_runner.get_eval_dataset") as mock_get:
            mock_get.return_value = [
                MagicMock(
                    query="test",
                    expected_sections=["Section 1"],
                    gold_answer="gold",
                    category=MagicMock(value="coverage"),
                    difficulty=MagicMock(value="easy"),
                )
            ]
            with patch("app.rag.eval_runner._run_retrieval_eval") as mock_retrieval:
                mock_retrieval.return_value = (FakeMetrics(), [{}])
                result = await run_evaluation(EvalConfig(mode="retrieval-only"))
        assert result.retrieval_metrics["recall_at_k"] == 1.0


# ===========================================================================
# app.rag.ingest
# ===========================================================================


class TestIngest:
    """Cover uncovered ingest paths."""

    def test_sliding_window_chunk_empty_text(self):
        from app.rag.ingest import sliding_window_chunk

        assert sliding_window_chunk("") == []
        assert sliding_window_chunk("   ") == []

    def test_chunk_policy_document_file_not_found(self):
        from app.rag.ingest import chunk_policy_document

        result = chunk_policy_document("/nonexistent/path/policy.md")
        assert result == []

    def test_chunk_policy_document_no_title_match(self):
        from app.rag.ingest import chunk_policy_document

        text = "Some content without title"
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(text)
            path = f.name
        try:
            result = chunk_policy_document(path)
            assert len(result) > 0
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_ingest_policy_no_path_configured(self):
        from app.config import Settings
        from app.rag.ingest import ingest_policy

        with patch("app.rag.ingest.get_settings") as mock_get_settings:
            mock_settings = Settings(policy_file_path="")
            mock_get_settings.return_value = mock_settings
            count = await ingest_policy()
        assert count == 0

    @pytest.mark.asyncio
    async def test_ingest_policy_file_not_found_returns_zero(self):
        from app.rag.ingest import ingest_policy

        with patch("app.rag.ingest.get_settings") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.policy_file_path = "/nonexistent/policy.md"
            mock_get_settings.return_value = mock_settings
            count = await ingest_policy()
        assert count == 0


# ===========================================================================
# app.rag.pgvector_store
# ===========================================================================


class TestPgVectorStore:
    """Cover uncovered pgvector_store paths."""

    def test_validate_identifier_unsafe_name(self):
        from app.rag.pgvector_store import _validate_identifier

        with pytest.raises(ValueError, match="Unsafe"):
            _validate_identifier("bad-name", "label")

    def test_validate_embedding_wrong_dimension(self):
        from app.rag.pgvector_store import _validate_embedding

        with pytest.raises(ValueError, match="has 2 dimensions"):
            _validate_embedding([1.0, 2.0], expected_dim=1536)

    def test_validate_embedding_non_finite_values(self):
        from app.rag.pgvector_store import _validate_embedding

        with pytest.raises(ValueError, match="not finite"):
            _validate_embedding([1.0, float("nan"), 3.0], expected_dim=3)

    def test_validate_embedding_non_numeric_value(self):
        from app.rag.pgvector_store import _validate_embedding

        with pytest.raises(TypeError, match="not a number"):
            _validate_embedding(["a", "b"], expected_dim=2)

    @pytest.mark.asyncio
    async def test_hybrid_search_exception_returns_empty(self):
        from app.rag.pgvector_store import PgVectorStore

        store = PgVectorStore(table_name="policy_chunks", id_field="id", embedding_dim=1536)
        with patch("app.rag.pgvector_store.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__.side_effect = Exception("DB down")
            result = await store.hybrid_search(
                query="test", embedding=[0.0] * 1536, n_results=5, threshold=1.0
            )
        assert result == []

    @pytest.mark.asyncio
    async def test_count_with_external_session(self):
        from app.rag.pgvector_store import PgVectorStore

        store = PgVectorStore(table_name="policy_chunks", id_field="id", embedding_dim=1536)
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 42
        mock_session.execute.return_value = mock_result
        count = await store.count(session=mock_session)
        assert count == 42

    def test_upsert_metadata_key_validation(self):
        from app.rag.pgvector_store import PgVectorStore

        store = PgVectorStore(table_name="policy_chunks", id_field="id", embedding_dim=1536)
        with pytest.raises(ValueError, match="Unsafe"):
            asyncio.run(
                store.upsert(
                    documents=[
                        {
                            "id": "1",
                            "text": "test",
                            "embedding": [0.0] * 1536,
                            "metadata": {"bad-key": "value"},
                        }
                    ]
                )
            )

    @pytest.mark.asyncio
    async def test_upsert_external_session(self):
        from app.rag.pgvector_store import PgVectorStore

        store = PgVectorStore(table_name="policy_chunks", id_field="id", embedding_dim=1536)
        mock_session = AsyncMock()
        await store.upsert(
            documents=[
                {"id": "1", "text": "test", "embedding": [0.0] * 1536}
            ],
            session=mock_session,
        )
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_exception_logged(self):
        from app.rag.pgvector_store import PgVectorStore

        store = PgVectorStore(table_name="policy_chunks", id_field="id", embedding_dim=1536)
        with patch("app.rag.pgvector_store.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__.side_effect = Exception("DB down")
            with pytest.raises(Exception, match="DB down"):
                await store.upsert(
                    documents=[
                        {"id": "1", "text": "test", "embedding": [0.0] * 1536}
                    ]
                )


# ===========================================================================
# app.rag.vector_store
# ===========================================================================


class TestVectorStore:
    """Cover uncovered vector_store paths."""

    def test_get_vector_store_unsupported_provider(self):
        from app.config import Settings
        from app.rag.vector_store import get_vector_store

        with patch("app.rag.vector_store.get_settings") as mock_get:
            mock_settings = Settings(vector_store_provider="unsupported")
            mock_get.return_value = mock_settings
            with pytest.raises(ValueError, match="Unsupported vector store provider"):
                get_vector_store(table_name="test", id_field="id")


# ===========================================================================
# app.rag.evaluation
# ===========================================================================


class TestEvaluation:
    """Cover uncovered evaluation paths."""

    def test_retrieval_metrics_empty_test_set(self):
        from app.rag.evaluation import RagEvaluationHarness

        harness = RagEvaluationHarness(test_set=[])
        metrics = asyncio.run(harness.evaluate(lambda q: []))
        assert metrics.total_queries == 0
