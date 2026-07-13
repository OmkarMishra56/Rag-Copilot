from openai import AsyncOpenAI

from app.config import get_settings
from app.core.chunking import count_tokens
from app.core.prompts import SUMMARY_PROMPT
from app.db.models import Message

settings = get_settings()
_client = AsyncOpenAI(api_key=settings.openai_api_key)


def build_token_aware_history(messages: list[Message], max_tokens: int) -> list[dict]:
    """Keeps as many recent turns as fit in max_tokens, dropping oldest first."""
    selected: list[dict] = []
    used = 0
    for msg in reversed(messages):
        t = msg.token_count or count_tokens(msg.content)
        if used + t > max_tokens:
            break
        selected.insert(0, {"role": msg.role, "content": msg.content})
        used += t
    return selected


async def maybe_summarize(messages: list[Message], existing_summary: str, trigger_turns: int) -> str | None:
    """Rolling summary memory: once conversation exceeds `trigger_turns`, compress older
    turns into a running summary so long conversations don't blow the context window."""
    if len(messages) < trigger_turns:
        return None

    older = messages[:-6]  # keep the most recent 6 turns verbatim, summarize the rest
    if not older:
        return None

    transcript = "\n".join(f"{m.role}: {m.content}" for m in older)
    prompt = f"{SUMMARY_PROMPT}\n\nPrevious summary: {existing_summary or 'none'}\n\nTranscript:\n{transcript}"

    response = await _client.chat.completions.create(
        model=settings.chat_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=300,
    )
    return response.choices[0].message.content
