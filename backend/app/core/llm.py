import json
from collections.abc import AsyncIterator

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.core.prompts import MULTI_QUERY_PROMPT, SELF_QUERY_PROMPT, SYSTEM_PROMPT

settings = get_settings()
_client = AsyncOpenAI(api_key=settings.openai_api_key)


async def stream_chat_completion(
    question: str,
    context_prompt: str,
    history: list[dict],
) -> AsyncIterator[str]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history, {"role": "user", "content": context_prompt}]
    stream = await _client.chat.completions.create(
        model=settings.chat_model,
        messages=messages,
        temperature=0.2,
        stream=True,
    )
    async for event in stream:
        delta = event.choices[0].delta.content if event.choices else None
        if delta:
            yield delta


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
async def generate_multi_queries(question: str, n: int = 3) -> list[str]:
    """Multi-query retriever: expands the user's question into n paraphrases to
    improve recall against a dense index that's sensitive to exact phrasing."""
    prompt = MULTI_QUERY_PROMPT.format(n=n, question=question)
    response = await _client.chat.completions.create(
        model=settings.chat_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=200,
    )
    try:
        queries = json.loads(response.choices[0].message.content)
        return [question, *[q for q in queries if isinstance(q, str)]]
    except (json.JSONDecodeError, TypeError):
        return [question]


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
async def extract_self_query_filters(question: str) -> tuple[dict, str]:
    """Self-query retriever: asks the LLM to pull structured metadata filters
    (e.g. 'in the PDF policy doc') out of a natural-language question."""
    prompt = SELF_QUERY_PROMPT.format(question=question)
    response = await _client.chat.completions.create(
        model=settings.chat_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=150,
    )
    try:
        parsed = json.loads(response.choices[0].message.content)
        return parsed.get("filters", {}), parsed.get("cleaned_query", question)
    except (json.JSONDecodeError, TypeError):
        return {}, question
