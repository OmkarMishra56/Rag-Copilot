import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: uuid.UUID
    filename: str
    source_type: str
    version: int
    status: str
    doc_metadata: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    document: DocumentOut
    message: str


class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    filters: dict | None = None


class SearchResultItem(BaseModel):
    text: str
    score: float
    metadata: dict


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
