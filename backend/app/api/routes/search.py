from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import enforce_rate_limit, get_current_user
from app.core.pipeline import hybrid_retrieve
from app.db.database import get_db
from app.db.models import User
from app.schemas.document import SearchRequest, SearchResponse, SearchResultItem

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse, dependencies=[Depends(enforce_rate_limit)])
async def search(
    payload: SearchRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
):
    candidates = await hybrid_retrieve(db, payload.query, filters=payload.filters)
    top = candidates[: payload.top_k]
    return SearchResponse(
        results=[
            SearchResultItem(text=c.text, score=c.retrieval_score, metadata=c.metadata) for c in top
        ]
    )
