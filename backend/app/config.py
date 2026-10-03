# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and .env file."""

    GEMINI_API_KEY: str = ""
    CHROMA_PATH: str = "./chroma_db"
    FRONTEND_URL: str = "http://localhost:5173"
    APP_NAME: str = "DocChat AI"

    # LLM model selection
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # RAG retrieval settings
    RETRIEVAL_TOP_K: int = 5
    RELEVANCE_THRESHOLD: float = 0.30  # cosine similarity cut-off (0–1 scale, lower=more similar in Chroma distance)

    # Debug mode: when True, logs retrieved chunks and full prompt
    DEBUG_MODE: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
