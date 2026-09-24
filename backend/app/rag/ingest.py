from __future__ import annotations

"""
RAG ingestion pipeline for OmniCare policy documents.

Reads policy markdown files, splits them into semantically coherent
overlapping chunks, and stores embeddings in a persistent Chroma vector DB.

Best practices applied:
- Sliding-window chunking with configurable overlap to respect embedding
  model context windows (all-MiniLM-L6-v2 max 256 tokens).
- Section title prepended to every sub-chunk for semantic context
  preservation across chunk boundaries.
- Idempotent: skips re-ingestion when the collection is already populated.
- Structured logging instead of print() for production log pipelines.

Can be run standalone: python -m app.rag.ingest
"""

import logging
import re
from pathlib import Path
from typing import Any

import chromadb
from chromadb.utils import embedding_functions

from app.config import settings

logger = logging.getLogger(__name__)


def sliding_window_chunk(text: str, window_size: int = 800, overlap: int = 150) -> list[str]:
    """
    Split text into overlapping fixed-size character windows.

    Attempts to break at natural paragraph/sentence/word boundaries within
    each window to preserve linguistic coherence. The overlap ensures that
    context at chunk edges is not lost between adjacent chunks.

    Args:
        text: The raw text body to chunk.
        window_size: Maximum characters per chunk (default 800, approx 180 tokens).
        overlap: Characters of overlap between consecutive chunks (default 150).

    Returns:
        List of non-empty text chunk strings.
    """
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + window_size

        if end < len(text):
            # Prefer breaking at a paragraph boundary first
            break_point = text.rfind("\n\n", start, end)
            if break_point == -1 or break_point < start + (window_size // 2):
                break_point = text.rfind("\n", start, end)
            if break_point == -1 or break_point < start + (window_size // 2):
                break_point = text.rfind(" ", start, end)
            if break_point != -1 and break_point > start:
                end = break_point

        chunks.append(text[start:end].strip())
        start = end - overlap
        if end >= len(text):
            break

    return [c for c in chunks if c]


def chunk_policy_document(filepath: str) -> list[dict[str, Any]]:
    """
    Parse a markdown policy document and produce a flat list of vector chunks.

    Each markdown ## section is independently chunked with a sliding window
    so that large sections stay within the embedding model context limit.
    The parent section title is prepended to every sub-chunk to preserve
    semantic context across chunk boundaries.

    Args:
        filepath: Absolute or relative path to the policy markdown file.

    Returns:
        List of dicts, each with keys:
            - id       (str): Unique chunk identifier.
            - text     (str): Chunk content for embedding and retrieval.
            - metadata (dict): Section name, source filename, chunk indices.

    Raises:
        FileNotFoundError: If the policy file does not exist.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Policy document not found: {filepath}")

    content = path.read_text(encoding="utf-8")

    # Split on ## section headers, keeping each header with its section body
    sections = re.split(r"(?=^## )", content, flags=re.MULTILINE)

    chunks: list[dict[str, Any]] = []
    for i, section in enumerate(sections):
        section_text = section.strip()
        if not section_text:
            continue

        # Extract the section title from the first line
        lines = section_text.split("\n")
        title = lines[0].lstrip("#").strip() if lines else f"Section {i}"

        # The body is everything after the header line
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else section_text

        # Skip a lone document title with no body
        if section_text.startswith("# ") and not body:
            continue

        # Produce overlapping sub-chunks from the section body
        body_chunks = sliding_window_chunk(body, window_size=800, overlap=150)

        for j, b_chunk in enumerate(body_chunks):
            # Prepend the section title to every sub-chunk so the embedding
            # captures full semantic context even in isolation.
            chunk_text = f"Section: {title}\n\n{b_chunk}"

            chunks.append(
                {
                    "id": f"policy_chunk_{i}_{j}",
                    "text": chunk_text,
                    "metadata": {
                        "section": title,
                        "source": path.name,
                        "chunk_index": i,
                        "sub_chunk_index": j,
                    },
                }
            )

    return chunks


def ingest_policy(
    policy_path: str | None = None,
    chroma_path: str | None = None,
    collection_name: str | None = None,
    embedding_model: str | None = None,
) -> int:
    """
    Ingest policy documents into the Chroma vector store.

    This function is idempotent: if the target collection already contains
    documents it returns the existing count without re-ingesting. Delete the
    collection manually to force a fresh ingestion.

    Args:
        policy_path: Path to the policy markdown file.
        chroma_path: Filesystem directory for Chroma storage.
        collection_name: Chroma collection name.
        embedding_model: Sentence-transformer model name.

    Returns:
        Number of chunks currently stored in the collection after this call.
    """
    policy_path = policy_path or settings.policy_file_path
    chroma_path = chroma_path or settings.chroma_db_path
    collection_name = collection_name or settings.chroma_collection_name
    embedding_model = embedding_model or settings.embedding_model

    client = chromadb.PersistentClient(path=chroma_path)

    embed_fn = embedding_functions.OpenAIEmbeddingFunction(api_key=settings.openai_api_key, model_name=embedding_model)  # noqa: E501

    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embed_fn,
    )

    # Idempotency guard: skip if already populated
    existing_count = collection.count()
    if existing_count > 0:
        logger.info(
            "Collection '%s' already contains %d documents - skipping ingestion.",
            collection_name,
            existing_count,
        )
        return existing_count

    chunks = chunk_policy_document(policy_path)

    if not chunks:
        logger.warning("No chunks extracted from '%s'. Ingestion aborted.", policy_path)
        return 0

    collection.add(
        ids=[c["id"] for c in chunks],
        documents=[c["text"] for c in chunks],
        metadatas=[c["metadata"] for c in chunks],
    )

    logger.info(
        "Ingested %d chunks into collection '%s'.",
        len(chunks),
        collection_name,
    )
    for chunk in chunks:
        logger.debug("  [%s] %s", chunk["id"], chunk["metadata"]["section"])

    return len(chunks)


if __name__ == "__main__":
    import logging as _logging

    _logging.basicConfig(level=_logging.INFO, format="%(levelname)s %(message)s")
    logger.info("Starting OmniCare policy document ingestion...")
    count = ingest_policy()
    logger.info("Ingestion complete. %d chunks stored.", count)
