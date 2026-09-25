"""
Retrieval-Augmented Generation (RAG) package for the OmniCare backend.

Handles policy document ingestion, vector storage in ChromaDB, hybrid
retrieval (vector + BM25 fallback), and embedding function configuration.
"""

from app.rag.ingest import ingest_policy, chunk_policy_document, sliding_window_chunk
from app.rag.retriever import retrieve, retrieve_hybrid, get_collection
from app.rag.embedding import EmbeddingFactory

__all__ = [
    "ingest_policy",
    "chunk_policy_document",
    "sliding_window_chunk",
    "retrieve",
    "retrieve_hybrid",
    "get_collection",
    "EmbeddingFactory",
]
