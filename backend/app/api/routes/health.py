import time

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.cache.redis_client import get_redis
from app.core import vectorstore
from app.db.database import get_db

router = APIRouter(tags=["system"])

REQUEST_COUNT = Counter("rag_requests_total", "Total requests", ["endpoint", "status"])
REQUEST_LATENCY = Histogram("rag_request_latency_seconds", "Request latency", ["endpoint"])
QUERY_LATENCY = Histogram("rag_query_latency_seconds", "End-to-end RAG query latency")


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    checks = {"postgres": False, "redis": False, "qdrant": False}

    try:
        await db.execute(text("SELECT 1"))
        checks["postgres"] = True
    except Exception:  # noqa: BLE001
        pass

    try:
        await get_redis().ping()
        checks["redis"] = True
    except Exception:  # noqa: BLE001
        pass

    try:
        await vectorstore._client.get_collections()
        checks["qdrant"] = True
    except Exception:  # noqa: BLE001
        pass

    healthy = all(checks.values())
    return Response(
        content=str({"status": "ok" if healthy else "degraded", "checks": checks, "timestamp": time.time()}),
        status_code=200 if healthy else 503,
        media_type="application/json",
    )


@router.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
