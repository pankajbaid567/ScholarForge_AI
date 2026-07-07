"""
ScholarForge_AI — FastAPI Application Entry Point.

Configures:
  - CORS middleware with configurable origins
  - Rate limiting middleware (Redis-backed)
  - Global exception handler
  - Lifespan-based startup/shutdown events
  - API route registration
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.routes import documents, chat, metrics
from src.database.session import engine
from src.database import models
from src.core.config import get_settings, setup_logging
from src.middleware.security import RateLimitMiddleware

logger = logging.getLogger("scholarforge.api")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Runs database table creation on startup (safe for development).
    In production, use Alembic migrations instead.
    """
    # --- Startup ---
    setup_logging()
    logger.info("ScholarForge_AI starting up...")

    # Create tables if they don't exist (idempotent)
    models.Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified")

    yield

    # --- Shutdown ---
    logger.info("ScholarForge_AI shutting down...")


app = FastAPI(
    title="ScholarForge_AI API",
    description=(
        "Production RAG System for Academic Research — "
        "Hybrid Search, Cross-Encoder Reranking, HyDE, "
        "Semantic Caching, and RAGAS Evaluation"
    ),
    version="2.1.0",
    lifespan=lifespan,
)


# --- Global Exception Handler ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catches unhandled exceptions and returns a clean JSON response
    instead of leaking internal stack traces to the client.
    """
    logger.error(
        "Unhandled exception on %s %s: %s",
        request.method,
        request.url.path,
        exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal server error occurred. Please try again later.",
            "type": type(exc).__name__,
        },
    )


# --- Middleware ---
# CORS — configurable via CORS_ORIGINS setting
cors_origins = [
    origin.strip()
    for origin in settings.CORS_ORIGINS.split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate Limiting — uses Redis-backed sliding window
app.add_middleware(
    RateLimitMiddleware,
    max_requests=settings.RATE_LIMIT_MAX_REQUESTS,
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
)


# --- Observability (optional) ---
try:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry import trace
    from openinference.instrumentation.openai import OpenAIInstrumentor
    from openinference.instrumentation.fastapi import FastAPIInstrumentor

    trace.set_tracer_provider(TracerProvider())
    trace.get_tracer_provider().add_span_processor(
        SimpleSpanProcessor(OTLPSpanExporter("http://localhost:6006/v1/traces"))
    )
    OpenAIInstrumentor().instrument()
    FastAPIInstrumentor.instrument_app(app)
    logger.info("OpenTelemetry observability enabled (Arize Phoenix)")
except ImportError:
    logger.info("Observability dependencies not installed; tracing disabled")


# --- Routes ---
app.include_router(documents.router, prefix="/api/v1/documents", tags=["Documents"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(metrics.router, prefix="/api/v1/metrics", tags=["Metrics"])


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for load balancers and monitoring."""
    return {"status": "healthy", "service": "ScholarForge_AI", "version": "2.1.0"}
