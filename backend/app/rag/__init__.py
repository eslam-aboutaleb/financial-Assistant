"""
Retrieval-Augmented Generation (RAG) package for the OmniCare backend.

Handles policy document ingestion, vector storage in pgvector, hybrid
retrieval using True Hybrid Search (RRF), and embedding function configuration.
"""

from app.rag.answer_evaluator import (
    AnswerMetrics,
    AnswerScore,
    evaluate_answer_heuristic,
    evaluate_answer_llm,
)
from app.rag.embedding import EmbeddingFactory
from app.rag.eval_dataset import (
    Difficulty,
    EvalSample,
    QuestionCategory,
    get_eval_dataset,
)
from app.rag.eval_runner import EvalConfig, EvalResult, run_evaluation
from app.rag.evaluation import LabeledQuery, RagEvaluationHarness, RetrievalMetrics
from app.rag.ingest import chunk_policy_document, ingest_policy, sliding_window_chunk
from app.rag.retriever import retrieve_hybrid

__all__ = [
    "ingest_policy",
    "chunk_policy_document",
    "sliding_window_chunk",
    "retrieve_hybrid",
    "EmbeddingFactory",
    "RagEvaluationHarness",
    "RetrievalMetrics",
    "LabeledQuery",
    "EvalSample",
    "QuestionCategory",
    "Difficulty",
    "get_eval_dataset",
    "AnswerScore",
    "AnswerMetrics",
    "evaluate_answer_heuristic",
    "evaluate_answer_llm",
    "EvalConfig",
    "EvalResult",
    "run_evaluation",
]

