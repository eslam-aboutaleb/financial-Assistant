"""
Retrieval-Augmented Generation (RAG) package for the OmniCare backend.

Handles policy document ingestion, vector storage in pgvector, hybrid
retrieval using True Hybrid Search (RRF), and embedding function configuration.
"""

from app.rag.ingest import ingest_policy, chunk_policy_document, sliding_window_chunk
from app.rag.retriever import retrieve_hybrid
from app.rag.embedding import EmbeddingFactory

__all__ = [
    "ingest_policy",
    "chunk_policy_document",
    "sliding_window_chunk",
    "retrieve_hybrid",
    "EmbeddingFactory",
]
