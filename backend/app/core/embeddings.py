import hashlib
import json

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.cache.redis_client import get_redis
from app.config import get_settings

settings = get_settings()
_client = AsyncOpenAI(api_key=settings.openai_api_key)


def _cache_key(text: str, model: str) -> str:
    digest = hashlib.sha256(f"{model}:{text}".encode()).hexdigest()
    return f"emb:{digest}"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
async def _embed_batch(texts: list[str], model: str) -> list[list[float]]:
    response = await _client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in response.data]


async def embed_texts(texts: list[str], model: str | None = None, use_cache: bool = True) -> list[list[float]]:
    """Embeds a batch of texts, using Redis as a content-addressed cache to avoid
    re-embedding identical chunks (common on document re-uploads / versioning)."""
    model = model or settings.embedding_model
    redis = get_redis() if use_cache else None

    results: list[list[float] | None] = [None] * len(texts)
    to_embed: list[tuple[int, str]] = []

    if redis:
        keys = [_cache_key(t, model) for t in texts]
        cached = await redis.mget(keys)
        for i, value in enumerate(cached):
            if value:
                results[i] = json.loads(value)
            else:
                to_embed.append((i, texts[i]))
    else:
        to_embed = list(enumerate(texts))

    if to_embed:
        fresh = await _embed_batch([t for _, t in to_embed], model)
        for (i, text), vector in zip(to_embed, fresh, strict=True):
            results[i] = vector
            if redis:
                await redis.set(_cache_key(text, model), json.dumps(vector), ex=settings.cache_ttl_seconds * 24)

    return results  # type: ignore[return-value]


async def embed_query(query: str, model: str | None = None) -> list[float]:
    vectors = await embed_texts([query], model=model, use_cache=True)
    return vectors[0]
