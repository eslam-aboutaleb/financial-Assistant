"""
Policy ingestion module for OmniCare Financial.

Reads the raw Markdown policy document, splits it into semantically meaningful,
overlapping chunks, and stores embeddings in the configured vector store.

Ingestion is idempotent: if the vector store already contains documents, the
process is skipped to avoid redundant embedding generation and storage costs.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import uuid
from typing import Any

from app.config import get_settings
from app.database import async_session_factory
from app.rag.embedding import EmbeddingFactory
from app.rag.vector_store import get_vector_store

logger = logging.getLogger(__name__)


def sliding_window_chunk(
    text: str,
    chunk_size: int = 600,
    overlap: int = 100,
) -> list[str]:
    """Split text into overlapping chunks based on word count.

    Uses a sliding window approach where each chunk contains ``chunk_size``
    words and subsequent chunks overlap by ``overlap`` words. This preserves
    context across chunk boundaries, which improves retrieval quality for
    queries that span section boundaries.

    Args:
        text: The input text to split into chunks.
        chunk_size: Maximum number of words per chunk. Defaults to 600.
        overlap: Number of words to overlap between consecutive chunks.
            Defaults to 100.

    Returns:
        list[str]: A list of text chunks. Returns an empty list if the input
        text is empty or contains no words.
    """
    words = text.split()
    chunks = []

    if not words:
        return []

    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i : i + chunk_size])
        chunks.append(chunk)
        if i + chunk_size >= len(words):
            break

    return chunks


def chunk_policy_document(filepath: str) -> list[dict[str, Any]]:
    """Parse a Markdown policy file into structured, overlapping chunks.

    The parser splits the document on Markdown ``##`` section headers to
    preserve semantic boundaries, then applies ``sliding_window_chunk`` to
    each section to create overlapping sub-chunks suitable for embedding.
    Each chunk is assigned a unique UUID and metadata describing its position
    within the document hierarchy.

    Args:
        filepath: Absolute or relative path to the Markdown policy document.

    Returns:
        list[dict]: A list of chunk dicts, each containing:
            - ``chunk_id`` (str): Unique chunk identifier (set during ingestion).
            - ``text`` (str): The chunk text content.
            - ``metadata`` (dict): Section, source filename, and chunk indices.
        Returns an empty list if the file is not found or cannot be read.
    """
    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        logger.error("Policy document not found at: %s", filepath)
        return []

    # Split on Markdown H2 headers to preserve section boundaries. The regex
    # captures the header title in group 1, allowing us to reconstruct the
    # document as alternating title/body pairs.
    sections = re.split(r"(?m)^##\s+(.*)$", content)

    preamble = sections[0].strip()
    parsed_sections = []
    if preamble:
        title_match = re.search(r"^#\s+(.+)$", preamble, re.MULTILINE)
        preamble_title = title_match.group(1).strip() if title_match else "Introduction"
        parsed_sections.append({"title": preamble_title, "content": preamble})

    for i in range(1, len(sections), 2):
        title = sections[i].strip()
        body = sections[i + 1].strip() if i + 1 < len(sections) else ""
        parsed_sections.append({"title": title, "content": body})

    chunks = []
    global_chunk_idx = 0

    source_filename = filepath.rsplit("/", maxsplit=1)[-1]

    for section in parsed_sections:
        section_title = section["title"]
        section_text = section["content"]

        # Reconstruct the full section text with its H2 header so that
        # the section title is included in the chunk content for better
        # retrieval context.
        full_text = f"## {section_title}\n\n{section_text}"
        sub_chunks = sliding_window_chunk(full_text)

        for sub_idx, sub_text in enumerate(sub_chunks):
            chunks.append(
                {
                    "id": str(uuid.uuid4()),
                    "text": sub_text,
                    "metadata": {
                        "chunk_id": f"policy_chunk_{global_chunk_idx}",
                        "section": section_title,
                        "source": source_filename,
                        "chunk_index": global_chunk_idx,
                        "sub_chunk_index": sub_idx,
                    },
                }
            )
            global_chunk_idx += 1

    return chunks


async def ingest_policy(
    policy_path: str | None = None,
) -> int:
    """Ingest policy documents into the configured vector store.

    This function is idempotent: it hashes the source file and stores the
    hash in ``policy_ingestion_meta``. If the file content has not changed
    since the last successful ingestion, the process is skipped. This makes
    it safe to call on every application startup.

    Args:
        policy_path: Optional explicit path to the policy Markdown file.
            If omitted, the path from ``app.config.Settings.policy_file_path``
            is used.

    Returns:
        int: The number of chunks currently stored in the vector store after
        this call. Returns 0 if no chunks could be extracted.
    """
    from sqlalchemy import text as sa_text  # noqa: PLC0415

    settings = get_settings()
    policy_path = policy_path or settings.policy_file_path

    if not policy_path:
        logger.warning("No policy_path configured; skipping ingestion.")
        return 0

    # Compute SHA-256 hash of the policy file contents.
    try:
        with open(policy_path, encoding="utf-8") as f:
            file_content = f.read()
    except FileNotFoundError:
        logger.warning("Policy document not found at '%s'; skipping ingestion.", policy_path)
        return 0

    source_hash = hashlib.sha256(file_content.encode("utf-8")).hexdigest()

    # Check if we have already ingested this exact content.
    async with async_session_factory() as session:
        result = await session.execute(
            sa_text("SELECT source_hash FROM policy_ingestion_meta WHERE source = :source"),
            {"source": policy_path},
        )
        row = result.mappings().first()
        stored_hash = row["source_hash"] if row else None

    if stored_hash == source_hash:
        existing_count = await get_vector_store(table_name="policy_chunks", id_field="id").count()
        logger.info(
            "Policy '%s' unchanged (hash %s); skipping ingestion. %d chunks already stored.",
            policy_path,
            source_hash[:12],
            existing_count,
        )
        return existing_count

    chunks = chunk_policy_document(policy_path)

    if not chunks:
        logger.warning("No chunks extracted from '%s'. Ingestion aborted.", policy_path)
        return 0

    embed_fn = EmbeddingFactory.get_embedding_function()
    texts = [c["text"] for c in chunks]
    embeddings = await embed_fn(texts)

    for chunk, emb in zip(chunks, embeddings, strict=True):
        chunk["embedding"] = emb

    source_filename = policy_path.rsplit("/", maxsplit=1)[-1]
    async with async_session_factory() as session:
        await session.execute(
            sa_text("DELETE FROM policy_chunks WHERE source = :source"),
            {"source": source_filename},
        )
        await session.commit()

    store = get_vector_store(table_name="policy_chunks", id_field="id")
    await store.upsert(chunks)

    # Record the ingestion hash so we can detect future changes.
    async with async_session_factory() as session:
        await session.execute(
            sa_text("""
                INSERT INTO policy_ingestion_meta (source, source_hash)
                VALUES (:source, :source_hash)
                ON CONFLICT (source) DO UPDATE SET
                    source_hash = EXCLUDED.source_hash,
                    ingested_at = now()
            """),
            {"source": policy_path, "source_hash": source_hash},
        )
        await session.commit()

    logger.info(
        "Ingested %d chunks from '%s' (hash %s).",
        len(chunks),
        policy_path,
        source_hash[:12],
    )
    return len(chunks)


if __name__ == "__main__":
    asyncio.run(ingest_policy())
