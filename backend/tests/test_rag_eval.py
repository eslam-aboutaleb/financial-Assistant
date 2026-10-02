"""
Tests for RAG Evaluation subsystem:
  - Evaluation dataset loading & filtering
  - Heuristic & LLM-as-judge answer evaluation
  - RAG evaluation harness & metrics
  - Evaluation runner (retrieval-only & end-to-end)
  - Evaluation API endpoints
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rag.answer_evaluator import (
    _key_fact_recall,
    _normalize_text,
    _token_overlap,
    evaluate_answer_heuristic,
    evaluate_answer_llm,
)
from app.rag.eval_dataset import (
    Difficulty,
    EvalSample,
    QuestionCategory,
    get_eval_dataset,
)
from app.rag.eval_runner import EvalConfig, run_evaluation
from app.rag.evaluation import LabeledQuery, RagEvaluationHarness, RetrievalMetrics


# ---------------------------------------------------------------------------
# Dataset tests
# ---------------------------------------------------------------------------


def test_eval_dataset_all():
    dataset = get_eval_dataset()
    assert len(dataset) >= 10
    for sample in dataset:
        assert isinstance(sample, EvalSample)
        assert sample.query
        assert len(sample.expected_sections) > 0
        assert sample.gold_answer
        assert isinstance(sample.category, QuestionCategory)
        assert isinstance(sample.difficulty, Difficulty)


def test_eval_dataset_filters():
    coverage_samples = get_eval_dataset(category=QuestionCategory.COVERAGE)
    assert len(coverage_samples) > 0
    assert all(s.category == QuestionCategory.COVERAGE for s in coverage_samples)

    easy_samples = get_eval_dataset(difficulty=Difficulty.EASY)
    assert len(easy_samples) > 0
    assert all(s.difficulty == Difficulty.EASY for s in easy_samples)

    empty_filtered = get_eval_dataset(
        category=QuestionCategory.DEDUCTIBLES,
        difficulty=Difficulty.HARD,
    )
    assert isinstance(empty_filtered, list)


# ---------------------------------------------------------------------------
# Answer evaluator tests (heuristic)
# ---------------------------------------------------------------------------


def test_normalize_text():
    raw = "  Hello, WORLD!! 123...  "
    norm = _normalize_text(raw)
    assert norm == "hello world 123"


def test_token_overlap():
    text_a = "Water damage from pipe burst"
    text_b = "Sudden pipe burst causing water damage"
    overlap = _token_overlap(text_a, text_b)
    assert overlap > 0.5

    assert _token_overlap("", "text") == 0.0
    assert _token_overlap("abc", "xyz") == 0.0


def test_key_fact_recall():
    gold = "Water damage is covered up to $25,000 with a $500 deductible."
    answer_good = "Sudden pipe burst is covered up to $25,000 with $500 deductible."
    score = _key_fact_recall(answer_good, gold)
    assert score >= 0.8

    answer_poor = "It is covered."
    score_poor = _key_fact_recall(answer_poor, gold)
    assert score_poor < score


def test_evaluate_answer_heuristic_empty():
    score = evaluate_answer_heuristic("query", "", "gold")
    assert score.overall == 0.0
    assert "Empty answer" in score.reasoning


def test_evaluate_answer_heuristic_good_match():
    query = "Is water damage from a pipe burst covered?"
    gold = "Yes, water damage caused by sudden pipe bursts is covered up to $25,000 with a $500 deductible."
    generated = (
        "According to Section 1, water damage caused by sudden pipe bursts "
        "is covered up to $25,000 with a $500 deductible."
    )
    context = (
        "## Section 1: Home Water Damage Coverage\n"
        "Water damage caused by sudden pipe bursts is covered up to $25,000 with a $500 deductible."
    )

    score = evaluate_answer_heuristic(
        query=query,
        answer=generated,
        gold_answer=gold,
        retrieved_context=context,
    )

    assert score.faithfulness > 0.4
    assert score.relevance > 0.3
    assert score.completeness > 0.6
    assert score.overall > 0.5


# ---------------------------------------------------------------------------
# Answer evaluator tests (LLM judge)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evaluate_answer_llm_success():
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({
        "faithfulness": 0.95,
        "relevance": 0.90,
        "completeness": 0.85,
        "conciseness": 1.0,
        "reasoning": "Accurate and grounded in context.",
    })
    mock_response.choices = [mock_choice]

    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_litellm:
        mock_litellm.return_value = mock_response

        score = await evaluate_answer_llm(
            query="Is water damage covered?",
            answer="Yes, sudden pipe bursts up to $25,000.",
            gold_answer="Yes, covered up to $25,000.",
            retrieved_context="Policy covers pipe bursts up to $25,000.",
        )

        assert score.faithfulness == 0.95
        assert score.relevance == 0.90
        assert score.completeness == 0.85
        assert score.overall > 0.8
        assert "Accurate" in score.reasoning


@pytest.mark.asyncio
async def test_evaluate_answer_llm_fallback_on_error():
    with patch("litellm.acompletion", new_callable=AsyncMock) as mock_litellm:
        mock_litellm.side_effect = RuntimeError("LiteLLM connection error")

        score = await evaluate_answer_llm(
            query="Is water damage covered?",
            answer="Yes, sudden pipe bursts up to $25,000 with $500 deductible.",
            gold_answer="Yes, sudden pipe bursts up to $25,000 with $500 deductible.",
            retrieved_context="Policy covers pipe bursts up to $25,000.",
        )

        assert score.reasoning.startswith("llm_judge_unavailable")
        assert "heuristic" in score.reasoning
        assert score.overall > 0.0


# ---------------------------------------------------------------------------
# Harness tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rag_evaluation_harness():
    harness = RagEvaluationHarness()
    harness.add_query(
        LabeledQuery(
            query="water damage",
            expected_chunk_ids={"chunk_1"},
        )
    )
    harness.add_query(
        LabeledQuery(
            query="jewelry limits",
            expected_chunk_ids={"chunk_2"},
        )
    )

    async def mock_retrieval(query: str):
        if "water" in query:
            return [{"id": "chunk_1", "document": "water text"}]
        return [{"id": "chunk_wrong", "document": "wrong"}]

    metrics: RetrievalMetrics = await harness.evaluate(mock_retrieval)
    assert metrics.total_queries == 2
    assert metrics.recall_at_k == 0.5
    assert metrics.precision_at_k == 0.5
    assert metrics.mrr == 0.5
    assert metrics.errors == 0


# ---------------------------------------------------------------------------
# Runner tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_evaluation_retrieval_only():
    mock_hybrid_results = [
        {
            "document": "Water damage caused by sudden pipe bursts is covered up to $25,000.",
            "metadata": {
                "section": "Section 1: Home Water Damage Coverage",
                "source": "sample_policy.md",
            },
            "distance": 0.3,
            "_rrf_score": 0.9,
        }
    ]

    with patch("app.rag.retriever.retrieve_hybrid", new_callable=AsyncMock) as mock_retrieve:
        mock_retrieve.return_value = mock_hybrid_results

        config = EvalConfig(
            mode="retrieval-only",
            category=QuestionCategory.COVERAGE,
            difficulty=Difficulty.EASY,
        )

        result = await run_evaluation(config)

        assert result.duration_seconds >= 0.0
        assert "Retrieval Metrics:" in result.summary
        assert "Answer Quality Metrics:" not in result.summary
        assert result.retrieval_metrics["recall_at_k"] > 0
        assert len(result.per_sample_results) > 0


@pytest.mark.asyncio
async def test_run_evaluation_end_to_end_heuristic():
    mock_hybrid_results = [
        {
            "document": "Water damage caused by sudden pipe bursts is covered up to $25,000 with a $500 deductible.",
            "metadata": {
                "section": "Section 1: Home Water Damage Coverage",
                "source": "sample_policy.md",
            },
            "distance": 0.2,
            "_rrf_score": 0.95,
        }
    ]

    with patch("app.rag.retriever.retrieve_hybrid", new_callable=AsyncMock) as mock_retrieve:
        mock_retrieve.return_value = mock_hybrid_results

        config = EvalConfig(
            mode="end-to-end",
            judge="heuristic",
            category=QuestionCategory.DEDUCTIBLES,
        )

        result = await run_evaluation(config)

        assert "Answer Quality Metrics:" in result.summary
        assert result.answer_metrics["avg_overall"] > 0.0
        assert len(result.per_sample_results) > 0
        assert "answer_faithfulness" in result.per_sample_results[0]


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


def test_api_list_eval_dataset(test_client, mock_current_user):
    response = test_client.get("/api/v1/rag/dataset", headers=mock_current_user)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 10
    assert "query" in data[0]
    assert "expected_sections" in data[0]

    # Filtered
    filtered_resp = test_client.get(
        "/api/v1/rag/dataset?category=coverage", headers=mock_current_user
    )
    assert filtered_resp.status_code == 200
    for item in filtered_resp.json():
        assert item["category"] == "coverage"

    # Invalid category
    bad_resp = test_client.get(
        "/api/v1/rag/dataset?category=invalid_category", headers=mock_current_user
    )
    assert bad_resp.status_code == 422


def test_api_evaluate_rag_endpoint(test_client, mock_current_user):
    mock_hybrid_results = [
        {
            "document": "Water damage caused by sudden pipe bursts is covered up to $25,000.",
            "metadata": {
                "section": "Section 1: Home Water Damage Coverage",
                "source": "sample_policy.md",
            },
            "distance": 0.2,
            "_rrf_score": 0.95,
        }
    ]

    with patch("app.rag.retriever.retrieve_hybrid", new_callable=AsyncMock) as mock_retrieve:
        mock_retrieve.return_value = mock_hybrid_results

        payload = {
            "mode": "end-to-end",
            "judge": "heuristic",
            "category": "coverage",
            "difficulty": "easy",
        }
        response = test_client.post(
            "/api/v1/rag/evaluate",
            json=payload,
            headers=mock_current_user,
        )
        assert response.status_code == 200
        data = response.json()
        assert "retrieval_metrics" in data
        assert "answer_metrics" in data
        assert "summary" in data
        assert data["duration_seconds"] >= 0

