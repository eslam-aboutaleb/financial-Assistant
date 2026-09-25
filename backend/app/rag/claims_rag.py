import logging
from typing import Any
import uuid

import chromadb
from chromadb.utils import embedding_functions
from sqlalchemy import select, text

from app.config import settings
from app.database import async_session_factory
from app.models.claim import Claim

logger = logging.getLogger(__name__)

_claims_collection_cache: dict[tuple[str, str, str], Any] = {}

def get_claims_collection() -> Any:
    chroma_path = settings.chroma_db_path
    collection_name = "omnicare_claims"
    embedding_model = settings.embedding_model

    cache_key = (chroma_path, collection_name, embedding_model)
    if cache_key not in _claims_collection_cache:
        client = chromadb.PersistentClient(path=chroma_path)
        embed_fn = embedding_functions.OpenAIEmbeddingFunction(
            api_key=settings.openai_api_key, model_name=embedding_model
        )
        _claims_collection_cache[cache_key] = client.get_or_create_collection(
            name=collection_name,
            embedding_function=embed_fn,
        )

    return _claims_collection_cache[cache_key]

async def _bm25_claims_fallback(
    query: str,
    user_id: uuid.UUID,
    n_results: int = 5,
) -> list[dict[str, Any]]:
    try:
        async with async_session_factory() as session:
            stmt = text("""
                SELECT claim_id, policy_number, claim_type, status, amount, description,
                       ts_rank(tsvector, plainto_tsquery('english', :query)) AS rank
                FROM claims
                WHERE owner_id = :owner_id AND tsvector @@ plainto_tsquery('english', :query)
                ORDER BY rank DESC
                LIMIT :limit
            """)
            params = {"query": query, "owner_id": user_id, "limit": n_results}
            result = await session.execute(stmt, params)
            rows = result.mappings().all()

        retrieved = []
        for row in rows:
            retrieved.append({
                "document": f"Claim {row['claim_id']}: {row['claim_type']} - {row['description']}",
                "metadata": {
                    "claim_id": row["claim_id"],
                    "policy_number": row["policy_number"],
                    "status": row["status"],
                    "amount": row["amount"],
                },
                "distance": 0.0,
                "_rank": float(row["rank"]),
                "_source": "bm25",
            })
        return retrieved
    except Exception as exc:
        logger.warning("BM25 fallback search failed for claims: %s", exc)
        return []

async def retrieve_claims_hybrid(
    query: str,
    user_id: uuid.UUID,
    n_results: int = 5,
    distance_threshold: float = 1.3,
) -> list[dict[str, Any]]:
    collection = get_claims_collection()

    # We use a where clause to filter by owner_id to secure the lookup!
    where_clause = {"owner_id": str(user_id)}

    available = collection.count()
    results = []

    if available > 0:
        raw = collection.query(
            query_texts=[query],
            n_results=min(n_results, available),
            where=where_clause
        )
        documents = raw.get("documents", [[]])[0]
        metadatas = raw.get("metadatas", [[]])[0]
        distances = raw.get("distances", [[]])[0]

        for doc, meta, dist in zip(documents, metadatas, distances, strict=False):
            if dist <= distance_threshold:
                results.append({"document": doc, "metadata": meta, "distance": dist})

    if results:
        return results

    logger.info("Falling back to BM25 keyword search for claims query: %s", query)
    return await _bm25_claims_fallback(query, user_id, n_results=n_results)

def ingest_claim_sync(
    claim_id: str,
    owner_id: uuid.UUID,
    claim_type: str,
    description: str,
    policy_number: str,
    status: str,
    amount: float,
):
    collection = get_claims_collection()
    text_content = f"Claim {claim_id}: {claim_type} - {description}"
    collection.add(
        ids=[claim_id],
        documents=[text_content],
        metadatas=[{
            "claim_id": claim_id,
            "owner_id": str(owner_id),
            "policy_number": policy_number,
            "status": status,
            "amount": amount
        }]
    )

async def ingest_all_claims():
    async with async_session_factory() as session:
        result = await session.execute(select(Claim))
        claims = result.scalars().all()

    for claim in claims:
        ingest_claim_sync(
            claim_id=claim.claim_id,
            owner_id=claim.owner_id,
            claim_type=claim.claim_type,
            description=claim.description,
            policy_number=claim.policy_number,
            status=claim.status,
            amount=claim.amount
        )
