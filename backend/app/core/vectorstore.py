import uuid

import numpy as np
from qdrant_client import AsyncQdrantClient, models

from app.config import get_settings

settings = get_settings()
_client = AsyncQdrantClient(url=settings.qdrant_url)


async def ensure_collection() -> None:
    collections = await _client.get_collections()
    names = {c.name for c in collections.collections}
    if settings.qdrant_collection not in names:
        await _client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=models.VectorParams(size=settings.embedding_dim, distance=models.Distance.COSINE),
        )
        # Payload indexes for fast metadata filtering
        for field, schema in [
            ("document_id", models.PayloadSchemaType.KEYWORD),
            ("source_type", models.PayloadSchemaType.KEYWORD),
            ("version", models.PayloadSchemaType.INTEGER),
            ("filename", models.PayloadSchemaType.KEYWORD),
        ]:
            await _client.create_payload_index(
                collection_name=settings.qdrant_collection, field_name=field, field_schema=schema
            )


async def upsert_chunks(points: list[dict]) -> None:
    """points: [{id, vector, payload}]"""
    await _client.upsert(
        collection_name=settings.qdrant_collection,
        points=[
            models.PointStruct(id=p["id"], vector=p["vector"], payload=p["payload"]) for p in points
        ],
    )


def _build_filter(filters: dict | None) -> models.Filter | None:
    if not filters:
        return None
    conditions = []
    for key, value in filters.items():
        if value is None:
            continue
        if isinstance(value, list):
            conditions.append(models.FieldCondition(key=key, match=models.MatchAny(any=value)))
        else:
            conditions.append(models.FieldCondition(key=key, match=models.MatchValue(value=value)))
    return models.Filter(must=conditions) if conditions else None


async def dense_search(
    query_vector: list[float], top_k: int = 25, filters: dict | None = None
) -> list[models.ScoredPoint]:
    result = await _client.query_points(
        collection_name=settings.qdrant_collection,
        query=query_vector,
        limit=top_k,
        query_filter=_build_filter(filters),
        with_payload=True,
        with_vectors=True,
    )
    return result.points


def mmr_select(
    query_vector: list[float], candidates: list[models.ScoredPoint], top_k: int = 10, lambda_mult: float = 0.5
) -> list[models.ScoredPoint]:
    """Maximal Marginal Relevance: balances relevance to the query against
    redundancy among already-selected results, improving diversity of context."""
    if not candidates:
        return []

    query_vec = np.array(query_vector)
    doc_vecs = {c.id: np.array(c.vector) for c in candidates if c.vector is not None}

    def cosine(a: np.ndarray, b: np.ndarray) -> float:
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        return float(np.dot(a, b) / denom) if denom else 0.0

    selected: list[models.ScoredPoint] = []
    remaining = list(candidates)

    while remaining and len(selected) < top_k:
        best_score = -1e9
        best_item = None
        for item in remaining:
            if item.id not in doc_vecs:
                continue
            relevance = cosine(query_vec, doc_vecs[item.id])
            redundancy = max(
                (cosine(doc_vecs[item.id], doc_vecs[s.id]) for s in selected if s.id in doc_vecs), default=0.0
            )
            mmr_score = lambda_mult * relevance - (1 - lambda_mult) * redundancy
            if mmr_score > best_score:
                best_score = mmr_score
                best_item = item
        if best_item is None:
            break
        selected.append(best_item)
        remaining.remove(best_item)

    return selected


async def delete_document_vectors(document_id: uuid.UUID) -> None:
    await _client.delete(
        collection_name=settings.qdrant_collection,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[models.FieldCondition(key="document_id", match=models.MatchValue(value=str(document_id)))]
            )
        ),
    )
