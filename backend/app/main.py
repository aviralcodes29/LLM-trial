"""FastAPI application entrypoint for DocChat AI — Phase 6: Production Hardening.

Features:
  1. JWT Authentication & multi-tenant user isolation.
  2. Slowapi rate limiting (20 chat/min, 10 uploads/hr).
  3. Token usage and cost tracking in Supabase PostgreSQL (raw psycopg2 SQL).
  4. Global exception handlers and structured error responses.
  5. Request logging middleware with timing and correlation IDs.
  6. Config-driven settings with environment variable overrides.
"""

import time
import uuid
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from app.config import settings
from app.db.database import init_db
from app.services.rate_limiter import limiter
from app.routes.auth import router as auth_router
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
# Lifespan Management (Database initialization)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context for startup and shutdown routines."""
    logger.info("Initializing Supabase PostgreSQL tables (schema.sql)...")
    try:
        init_db()
        logger.info("Supabase database initialized successfully.")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}", exc_info=True)
    yield
    logger.info("Application shutting down.")


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title=settings.APP_NAME,
    description="DocChat AI - Production-Hardened RAG API with JWT Auth, Supabase PostgreSQL, Rate Limiting & Usage Tracking",
    version="0.6.0",
    lifespan=lifespan,
)

# Attach Slowapi Limiter to app state
app.state.limiter = limiter


# ---------------------------------------------------------------------------
# Request Logging Middleware
# ---------------------------------------------------------------------------
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log incoming request method, path, execution time, and status code."""
    req_id = str(uuid.uuid4())[:8]
    start_time = time.perf_counter()
    client_ip = request.client.host if request.client else "unknown"

    logger.info(f"[{req_id}] --> {request.method} {request.url.path} from {client_ip}")

    try:
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000
        response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"
        response.headers["X-Request-ID"] = req_id
        logger.info(
            f"[{req_id}] <-- {response.status_code} {request.method} {request.url.path} ({duration_ms:.1f}ms)"
        )
        return response
    except Exception as exc:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.error(
            f"[{req_id}] <-- ERROR {request.method} {request.url.path} ({duration_ms:.1f}ms): {exc}",
            exc_info=True,
        )
        raise exc


# ---------------------------------------------------------------------------
# Global Exception Handlers
# ---------------------------------------------------------------------------
@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Structured handler for Slowapi 429 Rate Limit Exceeded events."""
    logger.warning(f"Rate limit exceeded on {request.method} {request.url.path}: {exc.detail}")
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "status": "error",
            "detail": f"Rate limit exceeded: {exc.detail}. Please slow down your requests.",
            "status_code": 429,
        },
    )


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """Standardized JSON error format for HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "detail": exc.detail,
            "status_code": exc.status_code,
        },
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def custom_validation_exception_handler(request: Request, exc: RequestValidationError):
    """Structured handler for Pydantic input validation failures."""
    errors = exc.errors()
    error_messages = [
        f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in errors
    ]
    detail_msg = "; ".join(error_messages)
    logger.warning(f"Input validation failed on {request.method} {request.url.path}: {detail_msg}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "detail": detail_msg,
            "validation_errors": errors,
            "status_code": 422,
        },
    )


@app.exception_handler(Exception)
async def custom_unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all handler for unhandled internal server errors."""
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "detail": "An internal server error occurred. Please try again later.",
            "status_code": 500,
        },
    )


# ---------------------------------------------------------------------------
# CORS Configuration
# ---------------------------------------------------------------------------
origins = [
    settings.FRONTEND_URL,
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"^https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Router Registration
# ---------------------------------------------------------------------------
app.include_router(auth_router)
app.include_router(upload_router)
app.include_router(chat_router)


# ---------------------------------------------------------------------------
# Health & Root Endpoints
# ---------------------------------------------------------------------------
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint to verify backend connectivity, database, and settings."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "debug_mode": settings.DEBUG_MODE,
        "require_auth": settings.REQUIRE_AUTH,
        "model": settings.GEMINI_MODEL,
        "rate_limits": {
            "chat": settings.RATE_LIMIT_CHAT,
            "upload": settings.RATE_LIMIT_UPLOAD,
        },
        "relevance_threshold": settings.RELEVANCE_THRESHOLD,
    }


@app.get("/", tags=["Root"])
async def root():
    """Root welcome endpoint."""
    return {
        "app": settings.APP_NAME,
        "status": "online",
        "docs_url": "/docs",
        "version": "0.6.0",
    }
