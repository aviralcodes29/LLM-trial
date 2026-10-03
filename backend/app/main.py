"""FastAPI application entrypoint for DocChat AI."""

import logging

# pyrefly: ignore [missing-import]
from fastapi import FastAPI
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes.upload import router as upload_router
from app.routes.chat import router as chat_router

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
log_level = logging.DEBUG if settings.DEBUG_MODE else logging.INFO
logging.basicConfig(
    level=log_level,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.APP_NAME,
    description="DocChat AI - Retrieval-Augmented Generation (RAG) backend API",
    version="0.3.0",
)

# CORS configuration
origins = [
    settings.FRONTEND_URL,
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers (Phase 2: Ingestion only — chat/retrieval reserved for Phase 3)
app.include_router(upload_router)
# app.include_router(chat_router)  # Reserved for Phase 3: RAG Retrieval & Chat


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint to verify backend connectivity."""
    return {
        "status": "ok",
        "debug_mode": settings.DEBUG_MODE,
        "model": settings.GEMINI_MODEL,
        "relevance_threshold": settings.RELEVANCE_THRESHOLD,
    }


@app.get("/", tags=["Root"])
async def root():
    """Root welcome endpoint."""
    return {
        "app": settings.APP_NAME,
        "status": "online",
        "docs_url": "/docs",
        "version": "0.3.0",
    }
