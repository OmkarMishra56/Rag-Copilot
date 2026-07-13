import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core import vectorstore
from app.core.chunking import adaptive_chunk
from app.core.embeddings import embed_texts
from app.core.loaders import checksum, infer_source_type, load_document
from app.core.sparse_search import tokenize
from app.db.models import Document, DocumentChunk, DocumentStatus
from app.db.repository import ChunkRepository, DocumentRepository
from app.utils.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


def clean_text(text: str) -> str:
    """Normalizes whitespace and strips boilerplate artifacts left by loaders."""
    lines = [line.rstrip() for line in text.splitlines()]
    lines = [line for line in lines if line.strip() or line == ""]
    cleaned = "\n".join(lines)
    while "\n\n\n" in cleaned:
        cleaned = cleaned.replace("\n\n\n", "\n\n")
    return cleaned.strip()


async def ingest_document(
    session: AsyncSession,
    raw: bytes,
    filename: str,
    uploaded_by: uuid.UUID | None = None,
    source_url: str = "",
) -> Document:
    doc_repo = DocumentRepository(session)
    chunk_repo = ChunkRepository(session)

    source_type = infer_source_type(filename)
    file_checksum = checksum(raw)
    version = await doc_repo.next_version(filename)

    document = await doc_repo.create(
        filename=filename,
        source_type=source_type,
        source_uri=source_url,
        version=version,
        status=DocumentStatus.PROCESSING.value,
        checksum=file_checksum,
        uploaded_by=uploaded_by,
    )

    try:
        loaded = load_document(raw, filename, source_type, source_url)
        text = clean_text(loaded.text)
        if not text:
            raise ValueError("Document produced no extractable text")

        pieces = adaptive_chunk(text, base_size=settings.chunk_size, overlap=settings.chunk_overlap)
        vectors = await embed_texts(pieces)

        db_chunks: list[DocumentChunk] = []
        vector_points: list[dict] = []

        for i, (piece, vector) in enumerate(zip(pieces, vectors, strict=True)):
            vector_id = str(uuid.uuid4())
            metadata = {
                "filename": filename,
                "source_type": source_type,
                "version": version,
                "document_id": str(document.id),
                **loaded.metadata,
            }
            db_chunks.append(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=i,
                    content=piece,
                    tokens=tokenize(piece),
                    chunk_metadata=metadata,
                    vector_id=vector_id,
                )
            )
            vector_points.append(
                {"id": vector_id, "vector": vector, "payload": {**metadata, "text": piece}}
            )

        await chunk_repo.bulk_add(db_chunks)
        await vectorstore.ensure_collection()
        await vectorstore.upsert_chunks(vector_points)

        await doc_repo.update_status(document.id, DocumentStatus.INDEXED.value)
        document.doc_metadata = {**loaded.metadata, "num_chunks": len(pieces)}
        logger.info("document_indexed", document_id=str(document.id), chunks=len(pieces), filename=filename)

    except Exception as exc:  # noqa: BLE001
        await doc_repo.update_status(document.id, DocumentStatus.FAILED.value)
        logger.error("document_ingestion_failed", document_id=str(document.id), error=str(exc))
        raise

    return document
