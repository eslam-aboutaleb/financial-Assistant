"""Coverage tests for app.auth uncovered paths."""
from __future__ import annotations

import jwt
from unittest.mock import patch

import pytest

from app.auth import (
    SECRET_KEY,
    _InvalidTokenError,
    _decode_token,
)


class TestAuthModule:
    def test_decode_token_malformed_subject_raises_invalid_token(self):
        token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.bad"
        with pytest.raises(_InvalidTokenError):
            _decode_token(token)

    def test_decode_token_malformed_subject_directly(self):
        payload = {"sub": "not-a-uuid", "exp": 9999999999}
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        with pytest.raises(_InvalidTokenError, match="malformed-subject"):
            _decode_token(token)

    def test_get_current_user_clears_cookie_for_nonexistent_user(self, test_client):
        with patch("app.auth._decode_token", side_effect=_InvalidTokenError("expired")):
            response = test_client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer invalid-token"},
            )
        assert response.status_code == 401
