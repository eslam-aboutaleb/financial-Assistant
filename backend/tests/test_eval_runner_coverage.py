"""Coverage tests for app.rag.eval_runner uncovered paths."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestEvalRunner:
    @pytest.mark.asyncio
    async def test_run_retrieval_eval_exception_in_sample(self):
        from app.rag.eval_runner import _run_retrieval_eval

        with patch(
            "app.rag.retriever.retrieve_hybrid",
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
        from app.rag.answer_evaluator import evaluate_answer_heuristic
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

    @pytest.mark.asyncio
    async def test_run_answer_eval_llm_judge(self):
        from app.rag.answer_evaluator import AnswerScore
        from app.rag.eval_runner import _run_answer_eval

        sample = MagicMock(query="test", gold_answer="gold answer")
        per_sample = [{"context": "some context", "chunks_found": 1}]

        llm_score = AnswerScore(
            faithfulness=0.9,
            relevance=0.8,
            completeness=0.7,
            conciseness=0.6,
            overall=0.75,
            reasoning="llm",
        )

        with patch(
            "app.rag.eval_runner.evaluate_answer_llm",
            new_callable=AsyncMock,
            return_value=llm_score,
        ):
            metrics, details = await _run_answer_eval(
                dataset=[sample],
                per_sample_retrieval=per_sample,
                judge="llm",
            )
        assert metrics.errors == 0
        assert metrics.avg_faithfulness == 0.9

    @pytest.mark.asyncio
    async def test_run_answer_eval_exception_in_sample(self):
        from app.rag.eval_runner import _run_answer_eval

        sample = MagicMock(query="test", gold_answer="gold")
        per_sample = [{"context": "", "chunks_found": 0}]

        with patch(
            "app.rag.eval_runner.evaluate_answer_heuristic",
            side_effect=Exception("eval failed"),
        ):
            metrics, details = await _run_answer_eval(
                dataset=[sample],
                per_sample_retrieval=per_sample,
                judge="heuristic",
            )
        assert metrics.errors == 1
        assert details[0].get("error") is not None

    def test_eval_runner_main_cli(self):
        from app.rag.eval_runner import main

        with patch("sys.argv", ["eval_runner", "--mode", "retrieval-only"]):
            with patch("app.rag.eval_runner.run_evaluation", new_callable=AsyncMock) as mock_run:

                @dataclass
                class FakeResult:
                    summary: str = "done"
                    per_sample_results: list = None

                    def __post_init__(self):
                        if self.per_sample_results is None:
                            self.per_sample_results = []

                mock_run.return_value = FakeResult()
                main()

    def test_eval_runner_main_cli_with_output(self, tmp_path):
        from app.rag.eval_runner import main

        output_file = tmp_path / "result.json"
        with patch(
            "sys.argv",
            [
                "eval_runner",
                "--mode",
                "retrieval-only",
                "--output",
                str(output_file),
            ],
        ):
            with patch("app.rag.eval_runner.run_evaluation", new_callable=AsyncMock) as mock_run:

                @dataclass
                class FakeResult:
                    summary: str = "done"
                    per_sample_results: list = None

                    def __post_init__(self):
                        if self.per_sample_results is None:
                            self.per_sample_results = []

                mock_run.return_value = FakeResult()
                main()
        assert output_file.exists()

    def test_eval_runner_main_output_writes_context_pop(self, tmp_path):
        from app.rag.eval_runner import main

        output_file = tmp_path / "eval_result.json"
        with patch(
            "sys.argv",
            [
                "eval_runner",
                "--mode",
                "retrieval-only",
                "--output",
                str(output_file),
            ],
        ):
            with patch("app.rag.eval_runner.run_evaluation", new_callable=AsyncMock) as mock_run:

                @dataclass
                class FakeResult:
                    summary: str = "done"
                    per_sample_results: list = None

                    def __post_init__(self):
                        if self.per_sample_results is None:
                            self.per_sample_results = [{"context": "some context", "query": "test"}]

                mock_run.return_value = FakeResult()
                main()
        assert output_file.exists()
        import json

        data = json.loads(output_file.read_text())
        for sample in data.get("per_sample_results", []):
            assert "context" not in sample
