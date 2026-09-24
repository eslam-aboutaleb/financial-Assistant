"""
Direct unit and integration tests for the RAG ingestion and retrieval modules.

Tests:
- test_ingest_creates_collection: Call ingest_policy with a temp directory, verify collection exists
- test_retrieve_water_damage_query: Ingest the sample policy, query 'water damage coverage',
  verify results contain relevant text about pipe bursts and $25,000
- test_retrieve_personal_property_query: Query 'electronics coverage', verify results
  mention $10,000 and personal property
- test_retrieve_returns_metadata: Verify results include section metadata
- test_retrieve_result_count: Query with n_results=1 returns exactly 1 result

Runs against real Chroma and real embeddings via sentence-transformers.
"""

import pytest
import chromadb

from app.config import settings
from app.rag.ingest import ingest_policy
from app.rag.retriever import retrieve


@pytest.fixture(scope="module")
def rag_chroma_dir(tmp_path_factory):
    """
    Module-scoped temporary Chroma directory with pre-ingested sample policy.
    Reused across retrieval tests for performance while maintaining test isolation.
    """
    temp_dir = str(tmp_path_factory.mktemp("rag_policy_chroma"))
    count = ingest_policy(chroma_path=temp_dir)
    assert count > 0, "Failed to ingest chunks into module-scoped Chroma store"
    return temp_dir


def test_ingest_creates_collection(tmp_path):
    """
    Test that calling ingest_policy with a fresh temporary directory
    creates the collection and populates it with document chunks.
    """
    temp_chroma = str(tmp_path / "new_chroma")
    count = ingest_policy(chroma_path=temp_chroma)

    assert count > 0, f"Expected count > 0 from ingest_policy, got {count}"

    # Verify directly via Chroma client that collection exists and has documents
    client = chromadb.PersistentClient(path=temp_chroma)
    collections = client.list_collections()
    collection_names = [col.name if hasattr(col, "name") else str(col) for col in collections]

    assert settings.chroma_collection_name in collection_names, (
        f"Collection '{settings.chroma_collection_name}' not found in Chroma. Existing: {collection_names}"
    )

    col = client.get_collection(name=settings.chroma_collection_name)
    assert col.count() == count, f"Expected {count} items in collection, found {col.count()}"


def test_retrieve_water_damage_query(rag_chroma_dir):
    """
    Test semantic retrieval for 'water damage coverage'.
    Verifies that the retrieved chunks contain relevant terms:
    'pipe bursts' and '$25,000'.
    """
    results = retrieve(query="water damage coverage", chroma_path=rag_chroma_dir)

    assert len(results) > 0, "No results returned for water damage query"

    combined_text = " ".join(r["document"] for r in results)
    assert "pipe bursts" in combined_text.lower(), (
        f"Expected 'pipe bursts' in retrieved text. Retrieved: {combined_text}"
    )
    assert "$25,000" in combined_text, (
        f"Expected '$25,000' in retrieved text. Retrieved: {combined_text}"
    )


def test_retrieve_personal_property_query(rag_chroma_dir):
    """
    Test semantic retrieval for 'electronics coverage'.
    Verifies that the results mention '$10,000' and 'personal property'.
    """
    results = retrieve(query="electronics coverage", chroma_path=rag_chroma_dir)

    assert len(results) > 0, "No results returned for electronics coverage query"

    combined_text = " ".join(r["document"] for r in results)
    assert "$10,000" in combined_text, (
        f"Expected '$10,000' in retrieved text. Retrieved: {combined_text}"
    )
    assert "personal property" in combined_text.lower(), (
        f"Expected 'personal property' in retrieved text. Retrieved: {combined_text}"
    )


def test_retrieve_returns_metadata(rag_chroma_dir):
    """
    Test that retrieval results include section metadata with required keys.
    """
    results = retrieve(query="water damage coverage", chroma_path=rag_chroma_dir)

    assert len(results) > 0, "No results returned to verify metadata"

    for r in results:
        assert "metadata" in r, f"Result missing 'metadata' field: {r}"
        metadata = r["metadata"]
        assert "section" in metadata, f"Metadata missing 'section': {metadata}"
        assert metadata["section"], "Metadata 'section' should not be empty"
        assert "source" in metadata, f"Metadata missing 'source': {metadata}"


def test_retrieve_result_count(rag_chroma_dir):
    """
    Test that retrieve respects the n_results parameter.
    Querying with n_results=1 must return exactly 1 result.
    """
    results = retrieve(query="insurance policy coverage", n_results=1, chroma_path=rag_chroma_dir)

    assert len(results) == 1, f"Expected exactly 1 result when n_results=1, got {len(results)}"
