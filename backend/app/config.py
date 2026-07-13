from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_name: str = "AI Customer Support Copilot"
    environment: str = "development"
    api_prefix: str = "/api/v1"

    # OpenAI
    openai_api_key: str = ""
    chat_model: str = "gpt-4.1"
    embedding_model: str = "text-embedding-3-large"
    embedding_dim: int = 3072

    # Postgres
    database_url: str = "postgresql+asyncpg://rag:rag@postgres:5432/rag_copilot"

    # Redis
    redis_url: str = "redis://redis:6379/0"
    cache_ttl_seconds: int = 3600

    # Qdrant
    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "support_docs"

    # Retrieval
    dense_top_k: int = 25
    sparse_top_k: int = 25
    hybrid_top_k: int = 15
    rerank_top_k: int = 6
    chunk_size: int = 800
    chunk_overlap: int = 120

    # Memory
    max_history_tokens: int = 3000
    summary_trigger_turns: int = 12

    # Security
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8
    max_upload_mb: int = 25
    rate_limit_per_minute: int = 60

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
