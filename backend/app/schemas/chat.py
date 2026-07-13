import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    chat_id: uuid.UUID | None = None
    question: str = Field(..., min_length=1, max_length=4000)
    filters: dict | None = None


class SourceCitation(BaseModel):
    index: int
    filename: str
    source_type: str | None = None
    version: int | None = None
    excerpt: str
    rerank_score: float


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    citations: list[dict] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatOut(BaseModel):
    id: uuid.UUID
    title: str
    summary: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatHistoryOut(BaseModel):
    chat: ChatOut
    messages: list[MessageOut]
