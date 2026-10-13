import time
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis_client import get_redis
from app.core import vectorstore
from app.db.database import get_db
from app.utils.logging import get_logger

router = APIRouter(tags=["system"])
logger = get_logger(__name__)

REQUEST_COUNT = Counter("rag_requests_total", "Total requests", ["endpoint", "status"])
REQUEST_LATENCY = Histogram("rag_request_latency_seconds", "Request latency", ["endpoint"])
QUERY_LATENCY = Histogram("rag_query_latency_seconds", "End-to-end RAG query latency")


@router.get("/health")
async def health(db: Annotated[AsyncSession, Depends(get_db)]):
    checks = {"postgres": False, "redis": False, "qdrant": False}

    try:
        await db.execute(text("SELECT 1"))
        checks["postgres"] = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("health_check_postgres_failed", error=str(exc))

    try:
        await get_redis().ping()
        checks["redis"] = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("health_check_redis_failed", error=str(exc))

    try:
        await vectorstore._client.get_collections()
        checks["qdrant"] = True
    except Exception as exc:  # noqa: BLE001
        logger.warning("health_check_qdrant_failed", error=str(exc))

    healthy = all(checks.values())
    return Response(
        content=str({"status": "ok" if healthy else "degraded", "checks": checks, "timestamp": time.time()}),
        status_code=200 if healthy else 503,
        media_type="application/json",
    )


@router.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
