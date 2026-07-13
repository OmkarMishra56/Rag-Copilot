from functools import lru_cache

from sentence_transformers import CrossEncoder

# Default to a small, fast cross-encoder for local dev; swap to
# "BAAI/bge-reranker-large" (or Cohere Rerank via API) for production accuracy.
DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


@lru_cache
def _get_model(model_name: str = DEFAULT_MODEL) -> CrossEncoder:
    return CrossEncoder(model_name)


class RerankCandidate:
    def __init__(self, chunk_id: str, text: str, metadata: dict, retrieval_score: float):
        self.chunk_id = chunk_id
        self.text = text
        self.metadata = metadata
        self.retrieval_score = retrieval_score
        self.rerank_score: float = 0.0


def rerank(query: str, candidates: list[RerankCandidate], top_k: int = 6, model_name: str = DEFAULT_MODEL) -> list[RerankCandidate]:
    if not candidates:
        return []
    model = _get_model(model_name)
    pairs = [(query, c.text) for c in candidates]
    scores = model.predict(pairs)
    for c, s in zip(candidates, scores, strict=True):
        c.rerank_score = float(s)
    return sorted(candidates, key=lambda c: c.rerank_score, reverse=True)[:top_k]
