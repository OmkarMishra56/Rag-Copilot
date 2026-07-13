import json
import re

from rank_bm25 import BM25Okapi
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis_client import get_redis
from app.db.repository import ChunkRepository

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")

BM25_INDEX_CACHE_KEY = "bm25:corpus:v1"
BM25_TTL = 600  # rebuild index every 10 min or on demand after ingestion


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


class BM25Index:
    def __init__(self, bm25: BM25Okapi, chunk_ids: list[str], texts: list[str]):
        self.bm25 = bm25
        self.chunk_ids = chunk_ids
        self.texts = texts

    def search(self, query: str, top_k: int = 25) -> list[tuple[str, float]]:
        scores = self.bm25.get_scores(tokenize(query))
        ranked = sorted(zip(self.chunk_ids, scores, strict=True), key=lambda x: x[1], reverse=True)
        return [(cid, score) for cid, score in ranked[:top_k] if score > 0]


async def build_bm25_index(session: AsyncSession) -> BM25Index:
    repo = ChunkRepository(session)
    chunks = await repo.all_for_bm25()
    corpus_tokens = [c.tokens if c.tokens else tokenize(c.content) for c in chunks]
    bm25 = BM25Okapi(corpus_tokens) if corpus_tokens else BM25Okapi([[""]])
    return BM25Index(
        bm25=bm25,
        chunk_ids=[str(c.vector_id) for c in chunks],
        texts=[c.content for c in chunks],
    )


async def invalidate_bm25_cache() -> None:
    redis = get_redis()
    await redis.delete(BM25_INDEX_CACHE_KEY)
