"""Coverage tests for app.api.v1.rag_eval uncovered paths."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch


class TestRagEvalAPI:
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

    def test_evaluate_rag_unexpected_exception_returns_500(self, test_client, mock_current_user):
        with patch("app.api.v1.rag_eval.run_evaluation", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = Exception("unexpected failure")
            response = test_client.post(
                "/api/v1/rag/evaluate",
                json={"mode": "retrieval-only", "judge": "heuristic"},
                headers=mock_current_user,
            )
        assert response.status_code == 500
