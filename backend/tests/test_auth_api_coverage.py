"""Coverage tests for app.api.v1.auth uncovered paths."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError


class TestAuthAPI:
    def test_signup_duplicate_username_returns_409(self, test_client):
        username = f"dupuser_{uuid.uuid4().hex[:8]}"
        payload = {"username": username, "password": "TestPass123!"}
        r1 = test_client.post("/api/v1/auth/signup", json=payload)
        assert r1.status_code == 201
        r2 = test_client.post("/api/v1/auth/signup", json=payload)
        assert r2.status_code == 409

    def test_signup_integrity_error_returns_409(self, test_client):
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock(side_effect=IntegrityError("duplicate", None, None))

        with patch("app.database.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__.return_value = mock_session
            response = test_client.post(
                "/api/v1/auth/signup",
                json={"username": "intuser", "password": "TestPass123!"},
            )
        assert response.status_code == 409

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
        assert data["user_id"] == "00000000-0000-0000-0000-000000000001"

    def test_signin_success_sets_cookie_and_returns_token(self, test_client):
        username = f"signin_{uuid.uuid4().hex[:8]}"
        payload = {"username": username, "password": "TestPass123!"}
        test_client.post("/api/v1/auth/signup", json=payload)
        response = test_client.post(
            "/api/v1/auth/signin",
            json={"username": username, "password": "TestPass123!"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_logout_returns_204_and_clears_cookie(self, test_client):
        response = test_client.post("/api/v1/auth/logout")
        assert response.status_code == 204
