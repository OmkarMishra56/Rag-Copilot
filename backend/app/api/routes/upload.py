from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import enforce_rate_limit, get_current_user
from app.config import get_settings
from app.core.ingestion import ingest_document
from app.core.sparse_search import invalidate_bm25_cache
from app.db.database import get_db
from app.db.models import User
from app.schemas.document import DocumentOut, DocumentUploadResponse

router = APIRouter(prefix="/upload", tags=["ingestion"])
settings = get_settings()


@router.post("", response_model=list[DocumentUploadResponse], dependencies=[Depends(enforce_rate_limit)])
async def upload_documents(
    files: list[UploadFile],
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="No files provided")

    responses = []
    for file in files:
        raw = await file.read()
        size_mb = len(raw) / (1024 * 1024)
        if size_mb > settings.max_upload_mb:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"{file.filename} exceeds {settings.max_upload_mb}MB limit",
            )
        try:
            document = await ingest_document(db, raw, file.filename, uploaded_by=user.id)
            await db.commit()
            responses.append(
                DocumentUploadResponse(document=DocumentOut.model_validate(document), message="Indexed successfully")
            )
        except ValueError as exc:
            await db.rollback()
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    await invalidate_bm25_cache()
    return responses
