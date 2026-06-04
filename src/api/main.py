from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry import trace
from openinference.instrumentation.openai import OpenAIInstrumentor
from openinference.instrumentation.fastapi import FastAPIInstrumentor
from src.api.routes import documents, chat, metrics
from src.database.session import engine
from src.database import models

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="ScholarForge_AI API",
    description="Production RAG System with Evaluation Dashboard",
    version="2.0.0",
)

# --- Observability Setup (Arize Phoenix) ---
trace.set_tracer_provider(TracerProvider())
# Assuming Phoenix is running locally or in docker-compose on port 6006
trace.get_tracer_provider().add_span_processor(
    SimpleSpanProcessor(OTLPSpanExporter("http://localhost:6006/v1/traces"))
)
OpenAIInstrumentor().instrument()
FastAPIInstrumentor.instrument_app(app)
# ------------------------------------------

# CORS middleware for Next.js/Streamlit UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router, prefix="/api/v1/documents", tags=["Documents"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(metrics.router, prefix="/api/v1/metrics", tags=["Metrics"])

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ScholarForge_AI"}
