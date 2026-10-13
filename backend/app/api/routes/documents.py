import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.core import vectorstore
from app.core.sparse_search import invalidate_bm25_cache
from app.db.database import get_db
from app.db.models import Role, User
from app.db.repository import DocumentRepository
from app.schemas.document import DocumentOut

router = APIRouter(prefix="/documents", tags=["documents"])
admin_user_dependency = require_role(Role.ADMIN)


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    limit: int = 50,
    offset: int = 0,
    source_type: str | None = None,
):
    repo = DocumentRepository(db)
    docs = await repo.list_all(limit=limit, offset=offset, source_type=source_type)
    return [DocumentOut.model_validate(d) for d in docs]


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
):
    repo = DocumentRepository(db)
    doc = await repo.get(document_id)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentOut.model_validate(doc)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(admin_user_dependency)],
):
    repo = DocumentRepository(db)
    doc = await repo.get(document_id)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Document not found")

    await vectorstore.delete_document_vectors(document_id)
    await repo.delete(document_id)
    await db.commit()
    await invalidate_bm25_cache()
