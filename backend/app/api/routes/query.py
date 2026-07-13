import json

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import enforce_rate_limit, get_current_user
from app.config import get_settings
from app.core.chunking import count_tokens
from app.core.memory import build_token_aware_history, maybe_summarize
from app.core.pipeline import run_rag_query
from app.core.security import mask_pii
from app.db.database import get_db
from app.db.models import User
from app.db.repository import ChatRepository, MessageRepository
from app.schemas.chat import QueryRequest

router = APIRouter(prefix="/query", tags=["query"])
settings = get_settings()


@router.post("", dependencies=[Depends(enforce_rate_limit)])
async def query(
    payload: QueryRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chat_repo = ChatRepository(db)
    msg_repo = MessageRepository(db)

    chat = await chat_repo.get(payload.chat_id) if payload.chat_id else None
    if chat is None:
        chat = await chat_repo.create(user.id, title=payload.question[:60])
        await db.commit()

    history_messages = await msg_repo.list_for_chat(chat.id)
    history = build_token_aware_history(history_messages, settings.max_history_tokens)

    summary = await maybe_summarize(history_messages, chat.summary, settings.summary_trigger_turns)
    if summary:
        await chat_repo.update_summary(chat.id, summary)
        await db.commit()

    await msg_repo.add(chat.id, "user", mask_pii(payload.question), token_count=count_tokens(payload.question))
    await db.commit()

    stream, sources = await run_rag_query(
        db, payload.question, history, history_summary=chat.summary, filters=payload.filters
    )

    async def event_generator():
        full_answer = []
        yield {"event": "sources", "data": json.dumps(sources)}
        async for token in stream:
            full_answer.append(token)
            yield {"event": "token", "data": token}

        answer_text = "".join(full_answer)
        await msg_repo.add(
            chat.id, "assistant", answer_text, citations=sources, token_count=count_tokens(answer_text)
        )
        await chat_repo.touch(chat.id)
        await db.commit()
        yield {"event": "done", "data": json.dumps({"chat_id": str(chat.id)})}

    return EventSourceResponse(event_generator())
