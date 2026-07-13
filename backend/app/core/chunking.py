import re
import uuid
from functools import lru_cache

import tiktoken

DEFAULT_SEPARATORS = ["\n\n## ", "\n\n# ", "\n\n", "\n", ". ", " "]


@lru_cache
def _get_encoder():
    """Lazily loads the tiktoken BPE file on first use (not at import time), so the
    app can still start in network-restricted environments. Returns None if the
    encoding can't be fetched, triggering a rough chars/4 fallback below."""
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception:  # noqa: BLE001
        return None


def count_tokens(text: str) -> int:
    encoder = _get_encoder()
    if encoder is None:
        return max(1, len(text) // 4)  # rough estimate if tiktoken's vocab file is unreachable
    return len(encoder.encode(text))


class Chunk:
    def __init__(self, text: str, index: int, parent_id: str | None = None, metadata: dict | None = None):
        self.id = str(uuid.uuid4())
        self.text = text
        self.index = index
        self.parent_id = parent_id
        self.metadata = metadata or {}


def _split_recursive(text: str, chunk_size: int, separators: list[str]) -> list[str]:
    """Recursive character/token-aware splitter: tries progressively finer separators."""
    if count_tokens(text) <= chunk_size:
        return [text] if text.strip() else []

    if not separators:
        # Hard split by token count as last resort
        encoder = _get_encoder()
        if encoder is None:
            # Fallback: approximate token-sized slices by character count (~4 chars/token)
            step = chunk_size * 4
            return [text[i : i + step] for i in range(0, len(text), step)]
        tokens = encoder.encode(text)
        return [encoder.decode(tokens[i : i + chunk_size]) for i in range(0, len(tokens), chunk_size)]

    sep, *rest = separators
    parts = text.split(sep)
    chunks: list[str] = []
    buffer = ""
    for part in parts:
        candidate = buffer + sep + part if buffer else part
        if count_tokens(candidate) <= chunk_size:
            buffer = candidate
        else:
            if buffer:
                chunks.extend(_split_recursive(buffer, chunk_size, rest))
            buffer = part
    if buffer:
        chunks.extend(_split_recursive(buffer, chunk_size, rest))
    return chunks


def _apply_overlap(chunks: list[str], overlap_tokens: int) -> list[str]:
    if overlap_tokens <= 0 or len(chunks) <= 1:
        return chunks
    encoder = _get_encoder()
    overlapped = [chunks[0]]
    for i in range(1, len(chunks)):
        if encoder is None:
            tail = chunks[i - 1][-(overlap_tokens * 4) :]
        else:
            prev_tokens = encoder.encode(chunks[i - 1])
            tail = (
                encoder.decode(prev_tokens[-overlap_tokens:]) if len(prev_tokens) > overlap_tokens else chunks[i - 1]
            )
        overlapped.append(tail + "\n" + chunks[i])
    return overlapped


def recursive_chunk(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    raw = _split_recursive(text, chunk_size, DEFAULT_SEPARATORS)
    return _apply_overlap([c.strip() for c in raw if c.strip()], overlap)


def semantic_chunk(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    """
    Lightweight semantic chunking: splits on paragraph/heading boundaries first
    (topic shifts), then falls back to recursive splitting only when a section
    still exceeds chunk_size. Avoids requiring a second embedding call per chunk boundary.
    """
    sections = re.split(r"\n(?=#{1,3}\s)|\n\n+", text)
    chunks: list[str] = []
    buffer = ""
    for section in sections:
        section = section.strip()
        if not section:
            continue
        candidate = f"{buffer}\n\n{section}" if buffer else section
        if count_tokens(candidate) <= chunk_size:
            buffer = candidate
        else:
            if buffer:
                chunks.append(buffer)
            if count_tokens(section) > chunk_size:
                chunks.extend(recursive_chunk(section, chunk_size, overlap))
                buffer = ""
            else:
                buffer = section
    if buffer:
        chunks.append(buffer)
    return _apply_overlap(chunks, overlap)


def adaptive_chunk(text: str, base_size: int = 800, overlap: int = 120) -> list[str]:
    """
    Adapts chunk size to document density: dense/technical text (API docs, code)
    gets smaller chunks for retrieval precision; prose gets larger chunks for context.
    """
    avg_line_len = sum(len(line) for line in text.splitlines()) / max(len(text.splitlines()), 1)
    is_dense = avg_line_len < 60 or bool(re.search(r"```|`\w+\(", text))
    size = int(base_size * 0.7) if is_dense else base_size
    return semantic_chunk(text, size, overlap)


def build_parent_child_chunks(
    text: str, parent_size: int = 2000, child_size: int = 400, overlap: int = 60
) -> tuple[list[Chunk], list[Chunk]]:
    """
    Small-to-big / parent-document retrieval: index small child chunks for precise
    dense retrieval, but return the larger parent chunk as context for the LLM.
    """
    parent_texts = recursive_chunk(text, parent_size, overlap=0)
    parents: list[Chunk] = []
    children: list[Chunk] = []
    for p_idx, p_text in enumerate(parent_texts):
        parent = Chunk(text=p_text, index=p_idx)
        parents.append(parent)
        child_texts = recursive_chunk(p_text, child_size, overlap)
        for c_idx, c_text in enumerate(child_texts):
            children.append(Chunk(text=c_text, index=c_idx, parent_id=parent.id))
    return parents, children
