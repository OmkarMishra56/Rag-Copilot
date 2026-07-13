import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, documents, health, history, query, search, upload
from app.config import get_settings
from app.core.vectorstore import ensure_collection
from app.db.database import init_models
from app.utils.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.environment)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup", environment=settings.environment)
    await init_models()
    await ensure_collection()
    yield
    logger.info("shutdown")


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Enterprise AI Customer Support Copilot powered by Retrieval-Augmented Generation.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_and_logging(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    response.headers["X-Process-Time"] = f"{duration:.4f}"
    logger.info(
        "request_handled",
        path=request.url.path,
        method=request.method,
        status_code=response.status_code,
        duration_ms=round(duration * 1000, 2),
    )
    return response


app.include_router(health.router, prefix=settings.api_prefix)
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(upload.router, prefix=settings.api_prefix)
app.include_router(query.router, prefix=settings.api_prefix)
app.include_router(documents.router, prefix=settings.api_prefix)
app.include_router(search.router, prefix=settings.api_prefix)
app.include_router(history.router, prefix=settings.api_prefix)


@app.get("/")
async def root():
    return {"service": settings.app_name, "status": "running", "docs": "/docs"}
