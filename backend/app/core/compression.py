import re

from app.core.chunking import count_tokens

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _keyword_overlap(query_terms: set[str], sentence: str) -> int:
    sentence_terms = set(re.findall(r"[a-zA-Z0-9_]+", sentence.lower()))
    return len(query_terms & sentence_terms)


def compress_chunk(query: str, text: str, max_tokens: int = 220) -> str:
    """Contextual compression: keeps only the sentences most relevant to the query
    instead of passing the full chunk to the LLM, reducing prompt size and noise.
    Falls back to a token-based truncation if the chunk is already short."""
    if count_tokens(text) <= max_tokens:
        return text

    query_terms = set(re.findall(r"[a-zA-Z0-9_]+", query.lower()))
    sentences = _SENTENCE_RE.split(text)
    scored = sorted(
        ((s, _keyword_overlap(query_terms, s)) for s in sentences),
        key=lambda x: x[1],
        reverse=True,
    )
    kept: list[str] = []
    used = 0
    # preserve original order among kept sentences for readability
    keep_set = {s for s, score in scored if score > 0}
    if not keep_set:
        keep_set = set(sentences[:3])

    for s in sentences:
        if s in keep_set:
            t = count_tokens(s)
            if used + t > max_tokens:
                break
            kept.append(s)
            used += t

    return " ".join(kept) if kept else text[: max_tokens * 4]
