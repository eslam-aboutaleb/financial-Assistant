from __future__ import annotations

"""
Policy RAG tool for the OmniCare agent.

Queries the Chroma vector store with distance thresholding and returns
grounded policy context with section citations for the LLM to answer from.
"""

from typing import Any

from app.rag.retriever import retrieve

# Distance threshold calibrated for all-MiniLM-L6-v2 on insurance text.
# Queries with no relevant policy match return an empty context rather than
# noise chunks, preventing the LLM from fabricating coverage details.
_DISTANCE_THRESHOLD = 1.3


def query_policy(query: str) -> dict[str, Any]:
    """Searches OmniCare insurance policy documents to answer coverage questions.

    Use this tool whenever the user asks about:
    - What is or is not covered under a policy
    - Coverage limits or maximum payout amounts
    - Deductibles or out-of-pocket amounts
    - Policy exclusions or conditions
    - Any general policy or insurance question

    The tool returns relevant policy text sections with citations. Always
    base your answer on the returned ``answer_context`` — do not add details
    that are not present in the context.

    Args:
        query (str): The user's policy coverage question or search topic.
            Example: "water damage from pipe burst"

    Returns:
        dict with keys:
            - ``answer_context`` (str): Concatenated relevant policy sections
              to use as grounding context in your answer.
            - ``sources`` (list[dict]): Unique source citations, each with
              ``section`` (str), ``source`` (str filename), and
              ``relevance_score`` (float, lower is more relevant).
            - ``chunks_found`` (int): Number of relevant chunks retrieved.
    """
    results = retrieve(query=query, n_results=5, distance_threshold=_DISTANCE_THRESHOLD)

    if not results:
        return {
            "answer_context": (
                "No relevant policy information found for this query. "
                "The user may be asking about something not covered in the policy documents, "
                "or should contact OmniCare support directly."
            ),
            "sources": [],
            "chunks_found": 0,
        }

    context_parts: list[str] = []
    sources: list[dict[str, Any]] = []
    seen_sections: set[str] = set()

    for result in results:
        doc_text = result["document"]
        metadata = result["metadata"]
        distance = result["distance"]
        section = metadata.get("section", "Unknown Section")
        source_file = metadata.get("source", "unknown")

        context_parts.append(f"[{section}]:\n{doc_text}")

        # Deduplicate citations — multiple overlapping sub-chunks from the
        # same section should not generate duplicate source entries.
        if section not in seen_sections:
            sources.append(
                {
                    "section": section,
                    "source": source_file,
                    "relevance_score": round(distance, 4),
                }
            )
            seen_sections.add(section)

    return {
        "answer_context": "\n\n---\n\n".join(context_parts),
        "sources": sources,
        "chunks_found": len(results),
    }
