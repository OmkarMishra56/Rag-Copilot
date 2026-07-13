from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core import llm, vectorstore
from app.core.compression import compress_chunk
from app.core.embeddings import embed_query
from app.core.prompts import build_context_block, build_user_prompt
from app.core.reranker import RerankCandidate, rerank
from app.core.security import detect_prompt_injection
from app.core.sparse_search import build_bm25_index
from app.utils.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class RetrievedSource:
    def __init__(self, index: int, text: str, metadata: dict, score: float):
        self.index = index
        self.text = text
        self.metadata = metadata
        self.score = score

    def to_dict(self) -> dict:
        return {"index": self.index, "text": self.text, "metadata": self.metadata, "score": self.score}


async def hybrid_retrieve(
    session: AsyncSession,
    query: str,
    filters: dict | None = None,
    use_multi_query: bool = True,
    use_mmr: bool = True,
) -> list[RerankCandidate]:
    """
    Dense (Qdrant) + Sparse (BM25) hybrid retrieval with reciprocal rank fusion,
    optional multi-query expansion, and MMR diversification before reranking.
    """
    queries = await llm.generate_multi_queries(query, n=2) if use_multi_query else [query]

    # --- Dense leg ---
    dense_results: dict[str, dict] = {}
    for q in queries:
        qvec = await embed_query(q)
        points = await vectorstore.dense_search(qvec, top_k=settings.dense_top_k, filters=filters)
        selected = mmr_or_all(qvec, points, use_mmr)
        for rank_i, point in enumerate(selected):
            entry = dense_results.setdefault(str(point.id), {"point": point, "rrf": 0.0})
            entry["rrf"] += 1.0 / (60 + rank_i)

    # --- Sparse leg (BM25) ---
    bm25_index = await build_bm25_index(session)
    sparse_scores: dict[str, float] = {}
    for q in queries:
        for rank_i, (chunk_id, _score) in enumerate(bm25_index.search(q, top_k=settings.sparse_top_k)):
            sparse_scores[chunk_id] = sparse_scores.get(chunk_id, 0.0) + 1.0 / (60 + rank_i)

    # --- Reciprocal rank fusion of dense + sparse ---
    fused_ids = set(dense_results) | set(sparse_scores)
    fused_scores = {
        cid: dense_results.get(cid, {}).get("rrf", 0.0) + sparse_scores.get(cid, 0.0) for cid in fused_ids
    }
    top_fused = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)[: settings.hybrid_top_k]

    candidates: list[RerankCandidate] = []
    text_by_id = {str(t[0]): t[1] for t in zip(bm25_index.chunk_ids, bm25_index.texts, strict=True)}

    for chunk_id, fused_score in top_fused:
        if chunk_id in dense_results:
            point = dense_results[chunk_id]["point"]
            text = point.payload.get("text", "")
            metadata = {k: v for k, v in point.payload.items() if k != "text"}
        else:
            text = text_by_id.get(chunk_id, "")
            metadata = {"vector_id": chunk_id}
        if not text:
            continue
        candidates.append(RerankCandidate(chunk_id=chunk_id, text=text, metadata=metadata, retrieval_score=fused_score))

    return candidates


def mmr_or_all(qvec: list[float], points, use_mmr: bool):
    if not use_mmr:
        return points
    return vectorstore.mmr_select(qvec, points, top_k=min(len(points), settings.dense_top_k), lambda_mult=0.6)


async def run_rag_query(
    session: AsyncSession,
    question: str,
    history: list[dict],
    history_summary: str = "",
    filters: dict | None = None,
) -> tuple[AsyncIterator[str], list[dict]]:
    """
    Full pipeline: self-query filter extraction -> hybrid retrieval -> rerank ->
    contextual compression -> prompt construction -> streaming generation.
    Returns (stream, sources) where sources are already resolved (non-streamed)
    for the frontend to render as citations alongside the streamed answer.
    """
    if detect_prompt_injection(question):
        logger.warning("possible_prompt_injection", question=question[:200])
        # We don't block the request outright (could be a legitimate question about
        # security), but we do NOT let it override the system prompt — the system
        # prompt already instructs the model to treat such phrases as untrusted content.

    extracted_filters, cleaned_query = await llm.extract_self_query_filters(question)
    merged_filters = {**(filters or {}), **extracted_filters}

    candidates = await hybrid_retrieve(session, cleaned_query, filters=merged_filters)
    top_ranked = rerank(cleaned_query, candidates, top_k=settings.rerank_top_k)

    sources: list[dict] = []
    context_chunks = []
    for i, c in enumerate(top_ranked, start=1):
        compressed = compress_chunk(cleaned_query, c.text)
        context_chunks.append({"index": i, "text": compressed, "metadata": c.metadata})
        sources.append(
            {
                "index": i,
                "filename": c.metadata.get("filename", "unknown"),
                "source_type": c.metadata.get("source_type"),
                "version": c.metadata.get("version"),
                "excerpt": compressed[:280],
                "rerank_score": round(c.rerank_score, 4),
            }
        )

    if not context_chunks:
        async def empty_stream() -> AsyncIterator[str]:
            yield (
                "I couldn't find anything in the knowledge base that answers this. "
                "Could you rephrase, or would you like me to route this to a human agent?"
            )

        return empty_stream(), []

    context_block = build_context_block(context_chunks)
    user_prompt = build_user_prompt(question, context_block, history_summary)

    stream = llm.stream_chat_completion(question, user_prompt, history)
    return stream, sources
