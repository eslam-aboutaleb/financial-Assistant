"""
Tier A golden contract tests for dual authentication and idempotency semantics.

Dual auth: the same endpoint must pass with a cookie only, pass with a bearer token
only, fail with neither, and let the bearer header win when both are present and the
bearer token is the invalid one.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.contract.conftest import SeededUser, _unique, compare_to_golden, signup

pytestmark = pytest.mark.contract


def test_cookie_only_is_accepted(contract_client: TestClient, user_a: SeededUser) -> None:
    """A session cookie alone authenticates the request."""
    response = contract_client.get("/api/v1/auth/me", cookies=user_a.cookies)
    assert response.status_code == 200
    assert response.json()["user_id"] == user_a.user_id


def test_bearer_only_is_accepted(contract_client: TestClient, user_a: SeededUser) -> None:
    """A bearer header alone authenticates the request."""
    response = contract_client.get("/api/v1/auth/me", headers=user_a.headers)
    assert response.status_code == 200
    assert response.json()["user_id"] == user_a.user_id


def test_no_credentials_is_rejected(contract_client: TestClient) -> None:
    """Neither source is a hard failure."""
    response = contract_client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_bearer_wins_over_cookie(contract_client: TestClient, user_a: SeededUser) -> None:
    """When both are present the bearer header wins, even if it is invalid."""
    user_b = signup(contract_client, _unique("auth_precedence_b"))

    response = contract_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-jwt"},
        cookies=user_a.cookies,
    )
    assert response.status_code == 401

    valid = contract_client.get(
        "/api/v1/auth/me",
        headers=user_b.headers,
        cookies=user_a.cookies,
    )
    assert valid.status_code == 200
    assert valid.json()["user_id"] == user_b.user_id


def test_signin_issues_a_usable_cookie(contract_client: TestClient, user_a: SeededUser) -> None:
    """A token from signin works as a cookie without any further exchange."""
    signed_in = contract_client.post(
        "/api/v1/auth/signin",
        json={"username": user_a.username, "password": user_a.password},
    )
    assert signed_in.status_code == 200
    token = signed_in.json()["access_token"]

    response = contract_client.get(
        "/api/v1/auth/me",
        cookies={"omnicare_access_token": token},
    )
    assert response.status_code == 200
    assert response.json()["user_id"] == user_a.user_id


def test_signout_only_clears_the_cookie(
    contract_client: TestClient,
    user_a: SeededUser,
) -> None:
    """Signout clears the browser cookie; the JWT itself stays valid until expiry.

    The access token is stateless, so replaying the same token after signout still
    authenticates. A client that discards the cookie is signed out from its own point
    of view, but a captured token remains usable for its full one-week lifetime. Frozen
    here because a future plan that adds server-side revocation must change this golden
    deliberately.
    """
    assert contract_client.post("/api/v1/auth/logout").status_code == 204

    response = contract_client.get("/api/v1/auth/me", headers=user_a.headers)
    assert response.status_code == 200
    assert response.json()["user_id"] == user_a.user_id


@pytest.mark.parametrize("endpoint", ["/api/v1/auth/me", "/api/v1/chat/conversations"])
def test_protected_endpoints_reject_anonymous(
    contract_client: TestClient,
    endpoint: str,
) -> None:
    """Every protected read endpoint rejects an anonymous caller identically."""
    response = contract_client.get(endpoint)
    assert response.status_code == 401
    compare_to_golden("auth_me_unauthenticated", response.json())
