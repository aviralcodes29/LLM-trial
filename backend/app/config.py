from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and .env file."""

    APP_NAME: str = "DocChat AI"
    ENVIRONMENT: str = "development"
    DEBUG_MODE: bool = False

    # URLs and CORS
    FRONTEND_URL: str = "http://localhost:5173"

    # Gemini LLM & Embeddings
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # Storage paths
    CHROMA_PATH: str = str(_BACKEND_DIR / "chroma_db")

    # ── Supabase / PostgreSQL connection ──────────────────────────────────────
    DB_HOST: str = "db.xxxxxxxxxxxxxxxxxxxx.supabase.co"
    DB_PORT: int = 5432
    DB_NAME: str = "postgres"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = ""
    DB_SSLMODE: str = "require"

    # JWT Authentication
    JWT_SECRET_KEY: str = "docchat-production-hardening-secret-key-phase6-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    REQUIRE_AUTH: bool = False  # When True, all requests must provide a valid JWT

    # Rate Limiting (slowapi format)
    RATE_LIMIT_CHAT: str = "20/minute"
    RATE_LIMIT_UPLOAD: str = "10/hour"

    # RAG retrieval settings
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 150
    RETRIEVAL_TOP_K: int = 3
    RELEVANCE_THRESHOLD: float = 0.30  # cosine similarity cut-off (0–1 scale)

    # Cost Tracking (USD per 1M tokens) - Gemini 1.5 Flash estimates
    INPUT_COST_PER_MILLION_TOKENS: float = 0.075
    OUTPUT_COST_PER_MILLION_TOKENS: float = 0.30

    model_config = SettingsConfigDict(
        env_file=(_BACKEND_DIR / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
