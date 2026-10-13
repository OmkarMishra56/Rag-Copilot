import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.db.repository import ChatRepository, MessageRepository
from app.schemas.chat import ChatHistoryOut, ChatOut, MessageOut

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=list[ChatOut])
async def list_chats(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    repo = ChatRepository(db)
    chats = await repo.list_for_user(user.id)
    return [ChatOut.model_validate(c) for c in chats]


@router.get("/{chat_id}", response_model=ChatHistoryOut)
async def get_chat_history(
    chat_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    chat_repo = ChatRepository(db)
    msg_repo = MessageRepository(db)
    chat = await chat_repo.get(chat_id)
    if not chat or chat.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Chat not found")
    messages = await msg_repo.list_for_chat(chat_id)
    return ChatHistoryOut(
        chat=ChatOut.model_validate(chat), messages=[MessageOut.model_validate(m) for m in messages]
    )
