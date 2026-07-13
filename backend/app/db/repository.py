import uuid
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chat, Document, DocumentChunk, Message


class ChatRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: uuid.UUID, title: str = "New conversation") -> Chat:
        chat = Chat(user_id=user_id, title=title)
        self.session.add(chat)
        await self.session.flush()
        return chat

    async def get(self, chat_id: uuid.UUID) -> Chat | None:
        result = await self.session.execute(select(Chat).where(Chat.id == chat_id))
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID, limit: int = 50) -> list[Chat]:
        result = await self.session.execute(
            select(Chat).where(Chat.user_id == user_id).order_by(Chat.updated_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def update_summary(self, chat_id: uuid.UUID, summary: str) -> None:
        chat = await self.get(chat_id)
        if chat:
            chat.summary = summary
            chat.updated_at = datetime.utcnow()

    async def touch(self, chat_id: uuid.UUID) -> None:
        chat = await self.get(chat_id)
        if chat:
            chat.updated_at = datetime.utcnow()


class MessageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(
        self, chat_id: uuid.UUID, role: str, content: str, citations: list | None = None, token_count: int = 0
    ) -> Message:
        message = Message(
            chat_id=chat_id, role=role, content=content, citations=citations or [], token_count=token_count
        )
        self.session.add(message)
        await self.session.flush()
        return message

    async def list_for_chat(self, chat_id: uuid.UUID, limit: int = 100) -> list[Message]:
        result = await self.session.execute(
            select(Message).where(Message.chat_id == chat_id).order_by(Message.created_at.asc()).limit(limit)
        )
        return list(result.scalars().all())

    async def recent(self, chat_id: uuid.UUID, n: int = 10) -> list[Message]:
        result = await self.session.execute(
            select(Message).where(Message.chat_id == chat_id).order_by(Message.created_at.desc()).limit(n)
        )
        return list(reversed(result.scalars().all()))


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **kwargs) -> Document:
        doc = Document(**kwargs)
        self.session.add(doc)
        await self.session.flush()
        return doc

    async def get(self, document_id: uuid.UUID) -> Document | None:
        result = await self.session.execute(select(Document).where(Document.id == document_id))
        return result.scalar_one_or_none()

    async def list_all(self, limit: int = 100, offset: int = 0, source_type: str | None = None) -> list[Document]:
        query = select(Document).order_by(Document.created_at.desc()).limit(limit).offset(offset)
        if source_type:
            query = query.where(Document.source_type == source_type)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_status(self, document_id: uuid.UUID, status: str) -> None:
        doc = await self.get(document_id)
        if doc:
            doc.status = status

    async def delete(self, document_id: uuid.UUID) -> None:
        await self.session.execute(delete(Document).where(Document.id == document_id))

    async def next_version(self, filename: str) -> int:
        result = await self.session.execute(
            select(Document.version).where(Document.filename == filename).order_by(Document.version.desc()).limit(1)
        )
        latest = result.scalar_one_or_none()
        return (latest or 0) + 1


class ChunkRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def bulk_add(self, chunks: list[DocumentChunk]) -> None:
        self.session.add_all(chunks)
        await self.session.flush()

    async def all_for_bm25(self) -> list[DocumentChunk]:
        """Loads full corpus for BM25 index build. In production this would be paginated/cached."""
        result = await self.session.execute(select(DocumentChunk))
        return list(result.scalars().all())

    async def get_by_vector_ids(self, vector_ids: list[str]) -> list[DocumentChunk]:
        result = await self.session.execute(select(DocumentChunk).where(DocumentChunk.vector_id.in_(vector_ids)))
        return list(result.scalars().all())
