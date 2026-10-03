"""Coverage tests for app.api.v1.health uncovered paths."""

from __future__ import annotations

from unittest.mock import patch


class TestHealthAPI:
    def test_health_check_db_failure(self, test_client):
        with patch("app.api.v1.health.asyncio.wait_for", side_effect=Exception("DB down")):
            response = test_client.get("/api/v1/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"

    def test_health_check_success(self, test_client):
        response = test_client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
