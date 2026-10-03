"""
RAG evaluation runner for OmniCare Financial.

Orchestrates end-to-end evaluation of the RAG pipeline by running the
curated test dataset through retrieval and answer generation, then
computing metrics across all dimensions.

Supports two modes:
  - **retrieval-only**: Evaluates retrieval quality (Recall@K, Precision@K, MRR)
  - **end-to-end**: Evaluates both retrieval and answer quality (faithfulness,
    relevance, completeness, conciseness)

Can be run as a CLI script or imported for use in tests and the eval API.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, UTC
from typing import Any

from app.rag.answer_evaluator import (
    AnswerMetrics,
    evaluate_answer_heuristic,
    evaluate_answer_llm,
)
from app.rag.eval_dataset import (
    Difficulty,
    EvalSample,
    QuestionCategory,
    get_eval_dataset,
)
from app.rag.evaluation import RetrievalMetrics

logger = logging.getLogger(__name__)


@dataclass
class EvalConfig:
    """Configuration for an evaluation run."""

    mode: str = "end-to-end"  # "retrieval-only" or "end-to-end"
    judge: str = "heuristic"  # "heuristic" or "llm"
    n_results: int = 5
    category: QuestionCategory | None = None
    difficulty: Difficulty | None = None


@dataclass
class EvalResult:
    """Complete results from an evaluation run."""

    timestamp: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    retrieval_metrics: dict[str, Any] = field(default_factory=dict)
    answer_metrics: dict[str, Any] = field(default_factory=dict)
    per_sample_results: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    duration_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Retrieval evaluation
# ---------------------------------------------------------------------------


async def _run_retrieval_eval(
    dataset: list[EvalSample],
    n_results: int = 5,
) -> tuple[RetrievalMetrics, list[dict[str, Any]]]:
    """Run retrieval evaluation using the existing RagEvaluationHarness.

    Maps EvalSample entries to LabeledQuery format and runs them through
    the hybrid retrieval pipeline.

    Returns:
        Tuple of (aggregated metrics, per-sample details).
    """
    from app.rag.retriever import retrieve_hybrid  # noqa: PLC0415

    per_sample: list[dict[str, Any]] = []

    async def _retrieval_fn(query: str) -> list[dict[str, Any]]:
        results = await retrieve_hybrid(query=query, n_results=n_results)
        return results

    for sample in dataset:
        start = time.monotonic()
        try:
            results = await _retrieval_fn(sample.query)
            latency_ms = (time.monotonic() - start) * 1000

            # Extract retrieved sections
            retrieved_sections = set()
            for r in results:
                section = r.get("metadata", {}).get("section", "")
                if section:
                    retrieved_sections.add(section)

            expected = set(sample.expected_sections)
            hits = expected & retrieved_sections
            recall = len(hits) / len(expected) if expected else 0.0
            precision = len(hits) / max(len(retrieved_sections), 1)

            # MRR: find rank of first relevant section
            mrr = 0.0
            for rank, r in enumerate(results, 1):
                section = r.get("metadata", {}).get("section", "")
                if section in expected:
                    mrr = 1.0 / rank
                    break

            # Build context for answer evaluation
            context_parts = [r.get("document", "") for r in results]
            context = "\n---\n".join(context_parts)

            per_sample.append(
                {
                    "query": sample.query,
                    "category": sample.category.value,
                    "difficulty": sample.difficulty.value,
                    "expected_sections": sample.expected_sections,
                    "retrieved_sections": list(retrieved_sections),
                    "recall": round(recall, 4),
                    "precision": round(precision, 4),
                    "mrr": round(mrr, 4),
                    "latency_ms": round(latency_ms, 2),
                    "chunks_found": len(results),
                    "context": context,
                }
            )
        except Exception as exc:
            logger.error("Retrieval eval failed for '%s': %s", sample.query, exc)
            per_sample.append(
                {
                    "query": sample.query,
                    "category": sample.category.value,
                    "difficulty": sample.difficulty.value,
                    "error": str(exc),
                }
            )

    # Compute aggregate retrieval metrics
    valid = [s for s in per_sample if "error" not in s]
    n = len(valid)
    metrics = RetrievalMetrics(
        recall_at_k=sum(s["recall"] for s in valid) / n if n else 0.0,
        precision_at_k=sum(s["precision"] for s in valid) / n if n else 0.0,
        mrr=sum(s["mrr"] for s in valid) / n if n else 0.0,
        avg_latency_ms=sum(s["latency_ms"] for s in valid) / n if n else 0.0,
        total_queries=len(dataset),
        errors=len(per_sample) - n,
    )

    return metrics, per_sample


# ---------------------------------------------------------------------------
# Answer quality evaluation
# ---------------------------------------------------------------------------


async def _run_answer_eval(
    dataset: list[EvalSample],
    per_sample_retrieval: list[dict[str, Any]],
    judge: str = "heuristic",
) -> tuple[AnswerMetrics, list[dict[str, Any]]]:
    """Run answer quality evaluation on the RAG pipeline output.

    Evaluates the retrieved context from the retrieval phase against gold
    answers. This avoids redundant retrieval calls and ensures the answer
    metrics are computed on the exact context used for retrieval metrics.

    Args:
        dataset: The evaluation samples.
        per_sample_retrieval: Retrieval results for each sample (provides context).
        judge: "heuristic" or "llm" evaluation strategy.

    Returns:
        Tuple of (aggregated metrics, per-sample answer details).
    """
    metrics = AnswerMetrics(total_evaluated=len(dataset))
    answer_details: list[dict[str, Any]] = []

    for i, sample in enumerate(dataset):
        try:
            retrieval_data = per_sample_retrieval[i] if i < len(per_sample_retrieval) else {}
            generated_answer = retrieval_data.get("context", "")
            chunks_found = retrieval_data.get("chunks_found", 0)

            if not generated_answer:
                generated_answer = "(no context retrieved)"

            if judge == "llm":
                score = await evaluate_answer_llm(
                    query=sample.query,
                    answer=generated_answer,
                    gold_answer=sample.gold_answer,
                    retrieved_context=generated_answer,
                )
            else:
                score = evaluate_answer_heuristic(
                    query=sample.query,
                    answer=generated_answer,
                    gold_answer=sample.gold_answer,
                    retrieved_context=generated_answer,
                )

            metrics.avg_faithfulness += score.faithfulness
            metrics.avg_relevance += score.relevance
            metrics.avg_completeness += score.completeness
            metrics.avg_conciseness += score.conciseness
            metrics.avg_overall += score.overall

            answer_details.append(
                {
                    "query": sample.query,
                    "gold_answer": sample.gold_answer,
                    "generated_answer": generated_answer[:500],
                    "chunks_found": chunks_found,
                    "faithfulness": score.faithfulness,
                    "relevance": score.relevance,
                    "completeness": score.completeness,
                    "conciseness": score.conciseness,
                    "overall": score.overall,
                    "reasoning": score.reasoning,
                }
            )

        except Exception as exc:
            logger.error("Answer eval failed for '%s': %s", sample.query, exc)
            metrics.errors += 1
            answer_details.append(
                {
                    "query": sample.query,
                    "error": str(exc),
                }
            )

    # Average the metrics
    n = metrics.total_evaluated - metrics.errors
    if n > 0:
        metrics.avg_faithfulness = round(metrics.avg_faithfulness / n, 4)
        metrics.avg_relevance = round(metrics.avg_relevance / n, 4)
        metrics.avg_completeness = round(metrics.avg_completeness / n, 4)
        metrics.avg_conciseness = round(metrics.avg_conciseness / n, 4)
        metrics.avg_overall = round(metrics.avg_overall / n, 4)

    metrics.per_sample = answer_details
    return metrics, answer_details


# ---------------------------------------------------------------------------
# Main evaluation runner
# ---------------------------------------------------------------------------


async def run_evaluation(config: EvalConfig | None = None) -> EvalResult:
    """Run a complete RAG evaluation.

    Args:
        config: Evaluation configuration. If None, uses defaults
            (end-to-end mode with heuristic judge).

    Returns:
        EvalResult with all metrics and per-sample details.
    """
    if config is None:
        config = EvalConfig()

    start_time = time.monotonic()
    result = EvalResult(
        timestamp=datetime.now(tz=UTC).isoformat(),
        config={
            "mode": config.mode,
            "judge": config.judge,
            "n_results": config.n_results,
            "category": config.category.value if config.category else None,
            "difficulty": config.difficulty.value if config.difficulty else None,
        },
    )

    # Load evaluation dataset
    dataset = get_eval_dataset(
        category=config.category,
        difficulty=config.difficulty,
    )

    if not dataset:
        result.summary = "No evaluation samples matched the filters."
        return result

    logger.info(
        "Starting RAG evaluation: mode=%s, judge=%s, samples=%d",
        config.mode,
        config.judge,
        len(dataset),
    )

    # Step 1: Retrieval evaluation
    retrieval_metrics, per_sample_retrieval = await _run_retrieval_eval(
        dataset=dataset,
        n_results=config.n_results,
    )
    result.retrieval_metrics = asdict(retrieval_metrics)

    # Step 2: Answer quality evaluation (if end-to-end mode)
    if config.mode == "end-to-end":
        answer_metrics, answer_details = await _run_answer_eval(
            dataset=dataset,
            per_sample_retrieval=per_sample_retrieval,
            judge=config.judge,
        )
        result.answer_metrics = {
            k: v for k, v in asdict(answer_metrics).items() if k != "per_sample"
        }

        # Merge per-sample results
        for i, retrieval_data in enumerate(per_sample_retrieval):
            merged = {**retrieval_data}
            if i < len(answer_details):
                merged.update(
                    {
                        f"answer_{k}": v
                        for k, v in answer_details[i].items()
                        if k not in ("query", "context")
                    }
                )
            result.per_sample_results.append(merged)
    else:
        result.per_sample_results = per_sample_retrieval

    result.duration_seconds = round(time.monotonic() - start_time, 2)

    # Build summary
    lines = [
        f"RAG Evaluation Complete ({config.mode} mode)",
        f"  Samples: {len(dataset)}",
        f"  Duration: {result.duration_seconds}s",
        "",
        "Retrieval Metrics:",
        f"  Recall@{config.n_results}: {retrieval_metrics.recall_at_k:.4f}",
        f"  Precision@{config.n_results}: {retrieval_metrics.precision_at_k:.4f}",
        f"  MRR: {retrieval_metrics.mrr:.4f}",
        f"  Avg Latency: {retrieval_metrics.avg_latency_ms:.1f}ms",
        f"  Errors: {retrieval_metrics.errors}",
    ]

    if config.mode == "end-to-end":
        lines.extend(
            [
                "",
                "Answer Quality Metrics:",
                f"  Faithfulness: {answer_metrics.avg_faithfulness:.4f}",
                f"  Relevance: {answer_metrics.avg_relevance:.4f}",
                f"  Completeness: {answer_metrics.avg_completeness:.4f}",
                f"  Conciseness: {answer_metrics.avg_conciseness:.4f}",
                f"  Overall: {answer_metrics.avg_overall:.4f}",
                f"  Errors: {answer_metrics.errors}",
            ]
        )

    result.summary = "\n".join(lines)
    logger.info("\n%s", result.summary)

    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for running RAG evaluation."""
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="Run OmniCare RAG evaluation")
    parser.add_argument(
        "--mode",
        choices=["retrieval-only", "end-to-end"],
        default="end-to-end",
        help="Evaluation mode (default: end-to-end)",
    )
    parser.add_argument(
        "--judge",
        choices=["heuristic", "llm"],
        default="heuristic",
        help="Answer evaluation strategy (default: heuristic)",
    )
    parser.add_argument(
        "--n-results",
        type=int,
        default=5,
        help="Number of retrieval results (default: 5)",
    )
    parser.add_argument(
        "--category",
        choices=[c.value for c in QuestionCategory],
        default=None,
        help="Filter by question category",
    )
    parser.add_argument(
        "--difficulty",
        choices=[d.value for d in Difficulty],
        default=None,
        help="Filter by difficulty level",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON file path for detailed results",
    )

    args = parser.parse_args()

    config = EvalConfig(
        mode=args.mode,
        judge=args.judge,
        n_results=args.n_results,
        category=QuestionCategory(args.category) if args.category else None,
        difficulty=Difficulty(args.difficulty) if args.difficulty else None,
    )

    logging.basicConfig(level=logging.INFO)
    result = asyncio.run(run_evaluation(config))

    print("\n" + result.summary)

    if args.output:
        output_data = asdict(result)
        # Remove large context fields from per-sample to keep output clean
        for sample in output_data.get("per_sample_results", []):
            sample.pop("context", None)

        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2, default=str)
        print(f"\nDetailed results saved to: {args.output}")


if __name__ == "__main__":
    main()
