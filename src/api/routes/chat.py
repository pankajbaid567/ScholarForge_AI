"""
Chat API routes with Server-Sent Events (SSE) streaming.

Orchestrates the full RAG pipeline:
  1. Semantic Cache check
  2. Session management & conversation memory
  3. HyDE query expansion
  4. Hybrid Search (Dense + Sparse/BM25 via RRF)
  5. Cross-Encoder Reranking (async, non-blocking)
  6. Context Building with citation metadata
  7. LLM streaming via SSE
  8. Background RAGAS evaluation dispatch
"""
import json
import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSessionOrm
from openai import AsyncOpenAI
from huggingface_hub import AsyncInferenceClient

from src.database.session import get_db
from src.database.models import (
    Session as DbSession,
    ConversationHistory,
    MessageRole,
    HumanFeedback,
)
from src.generation.context_builder import ContextBuilder
from src.generation.memory import MemoryManager
from src.api.dependencies import get_hybrid_search, get_reranker
from src.core.config import get_settings
from src.workers.celery_app import task_run_ragas
from src.retrieval.semantic_cache import get_semantic_cache
from src.retrieval.hyde import HyDEExpander

logger = logging.getLogger("scholarforge.api.chat")
router = APIRouter()
settings = get_settings()

# --- LLM Client Initialization ---
openai_client = (
    AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    if settings.OPENAI_API_KEY
    else None
)
hf_client = (
    AsyncInferenceClient(token=settings.HUGGINGFACE_API_KEY)
    if (not settings.OPENAI_API_KEY and settings.HUGGINGFACE_API_KEY)
    else None
)


# --- Request / Response Models ---
class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(..., min_length=1, max_length=5000)
    stream: bool = True


class FeedbackRequest(BaseModel):
    vote: int = Field(..., ge=-1, le=1)
    comment: str = None


# --- Helpers ---
def _get_or_create_session(db: DbSessionOrm, session_id: str) -> DbSession:
    """Retrieves an existing session or creates a new one."""
    session = db.query(DbSession).filter(DbSession.id == session_id).first()
    if not session:
        try:
            # Validate that session_id is a valid UUID
            uuid.UUID(session_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="session_id must be a valid UUID",
            )
        session = DbSession(id=session_id)
        db.add(session)
        db.commit()
        db.refresh(session)
        logger.info("Created new session: %s", session_id)
    return session


def _save_message(
    db: DbSessionOrm,
    session_id,
    role: MessageRole,
    content: str,
    context_used: list = None,
) -> ConversationHistory:
    """Persists a message to the conversation history."""
    msg = ConversationHistory(
        session_id=session_id,
        role=role,
        content=content,
        context_used=context_used or [],
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


# --- Streaming Generator ---
async def _llm_stream(
    prompt: str,
    history: list,
    top_chunks: list,
    start_time: float,
    retrieval_latency_ms: int,
    message_id: str,
    request_msg: str,
    db: DbSessionOrm,
):
    """
    SSE streaming generator that interacts with the configured LLM provider.
    After streaming completes, it updates the assistant message in the DB,
    stores the response in the semantic cache, and dispatches a background
    RAGAS evaluation.
    """
    messages = [{"role": "system", "content": prompt}] + history
    full_response = ""

    try:
        if openai_client:
            stream = await openai_client.chat.completions.create(
                model=settings.LLM_MODEL_NAME,
                messages=messages,
                stream=True,
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=settings.LLM_TEMPERATURE,
            )
            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    full_response += content
                    yield f"data: {json.dumps({'delta': content})}\n\n"

        elif hf_client:
            stream = await hf_client.chat_completion(
                model=settings.LLM_MODEL_NAME,
                messages=messages,
                stream=True,
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=settings.LLM_TEMPERATURE,
            )
            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    full_response += content
                    yield f"data: {json.dumps({'delta': content})}\n\n"
        else:
            yield f"data: {json.dumps({'error': 'No LLM provider configured'})}\n\n"
            return

    except Exception as e:
        logger.error("LLM streaming error: %s", e, exc_info=True)
        yield f"data: {json.dumps({'error': f'LLM error: {str(e)}'})}\n\n"
        return

    # --- Post-stream actions ---
    chat_latency_ms = int((time.time() - start_time) * 1000)
    llm_latency_ms = chat_latency_ms - retrieval_latency_ms
    context_list = [c.get("text", "") for c in top_chunks]

    # Send final metadata block
    metadata = {
        "latency_ms": chat_latency_ms,
        "retrieval_latency_ms": retrieval_latency_ms,
        "llm_latency_ms": llm_latency_ms,
        "context_chunks": [c.get("id", "unknown") for c in top_chunks],
        "cache_hit": False,
    }
    yield f"data: {json.dumps({'metadata': metadata})}\n\n"

    # Update the assistant message with the full response content
    try:
        assistant_msg = (
            db.query(ConversationHistory)
            .filter(ConversationHistory.id == message_id)
            .first()
        )
        if assistant_msg:
            assistant_msg.content = full_response
            db.commit()
    except Exception as e:
        logger.error("Failed to update assistant message content: %s", e)

    # Store in Semantic Cache
    try:
        cache = get_semantic_cache()
        cache.store_cache(request_msg, full_response)
    except Exception as e:
        logger.warning("Failed to store response in semantic cache: %s", e)

    # Dispatch background RAGAS evaluation
    try:
        task_run_ragas.apply_async(
            args=[
                str(message_id),
                request_msg,
                full_response,
                context_list,
                chat_latency_ms,
                retrieval_latency_ms,
                llm_latency_ms,
            ],
            queue="evaluation",
        )
        logger.info("Dispatched RAGAS evaluation for message %s", message_id)
    except Exception as e:
        logger.warning("Failed to dispatch RAGAS evaluation: %s", e)


# --- Routes ---
@router.post("/stream")
async def chat_stream(request: ChatRequest, db: DbSessionOrm = Depends(get_db)):
    """
    Primary chat endpoint with SSE streaming response.
    Orchestrates the full RAG pipeline.
    """
    start_time = time.time()

    if not settings.OPENAI_API_KEY and not settings.HUGGINGFACE_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="No LLM API key is configured. Set OPENAI_API_KEY or HUGGINGFACE_API_KEY.",
        )

    # 1. Session Management
    session = _get_or_create_session(db, request.session_id)

    # 2. Semantic Cache Check
    try:
        cache = get_semantic_cache()
        cached_response = cache.check_cache(request.message)
    except Exception as e:
        logger.warning("Semantic cache check failed (%s); proceeding without cache", e)
        cached_response = None

    if cached_response:
        logger.info("Cache HIT for query: %.50s...", request.message)
        _save_message(db, session.id, MessageRole.USER, request.message)
        _save_message(db, session.id, MessageRole.ASSISTANT, cached_response)

        async def cached_stream():
            latency_ms = int((time.time() - start_time) * 1000)
            yield f"data: {json.dumps({'delta': cached_response})}\n\n"
            metadata = {"latency_ms": latency_ms, "context_chunks": [], "cache_hit": True}
            yield f"data: {json.dumps({'metadata': metadata})}\n\n"

        return StreamingResponse(cached_stream(), media_type="text/event-stream")

    # 3. Save User Message
    _save_message(db, session.id, MessageRole.USER, request.message)

    # 4. Fetch Conversation History
    db_history = (
        db.query(ConversationHistory)
        .filter(ConversationHistory.session_id == session.id)
        .order_by(ConversationHistory.created_at.asc())
        .all()
    )
    memory_manager = MemoryManager(max_tokens=settings.MEMORY_MAX_TOKENS)
    formatted_history = memory_manager.format_history(db_history)

    # 5. Query Expansion (HyDE)
    expander = HyDEExpander()
    expanded_query = await expander.expand_query(request.message)

    # 6. Hybrid Search (Dense + Sparse via RRF)
    hybrid_search = get_hybrid_search()
    top_candidates = hybrid_search.search(expanded_query, k=settings.HYBRID_SEARCH_K)

    # 7. Reranking (async — offloaded to thread pool to avoid blocking the event loop)
    reranker = get_reranker()
    top_chunks = await reranker.arerank(
        request.message, top_candidates, top_k=settings.RERANKER_TOP_K
    )

    # 8. Context Building
    builder = ContextBuilder()
    system_prompt = builder.build_system_prompt(top_chunks)

    # 9. Pre-create Assistant Message record (content updated after streaming)
    context_ids = [c.get("id", "unknown") for c in top_chunks]
    assistant_msg = _save_message(
        db, session.id, MessageRole.ASSISTANT, "", context_used=context_ids
    )

    retrieval_latency_ms = int((time.time() - start_time) * 1000)

    logger.info(
        "RAG pipeline complete — %d candidates → %d reranked (took %dms) — streaming response",
        len(top_candidates),
        len(top_chunks),
        retrieval_latency_ms,
    )

    # 10. Stream Response
    return StreamingResponse(
        _llm_stream(
            system_prompt,
            formatted_history,
            top_chunks,
            start_time,
            retrieval_latency_ms,
            str(assistant_msg.id),
            request.message,
            db,
        ),
        media_type="text/event-stream",
    )


@router.post("/query")
async def simple_query(request: ChatRequest, db: DbSessionOrm = Depends(get_db)):
    """
    Non-streaming query endpoint for programmatic access.
    """
    if not settings.OPENAI_API_KEY and not settings.HUGGINGFACE_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="No LLM API key is configured. Set OPENAI_API_KEY or HUGGINGFACE_API_KEY.",
        )

    # Semantic Cache Check
    try:
        cache = get_semantic_cache()
        cached_response = cache.check_cache(request.message)
        if cached_response:
            return {"answer": cached_response, "context_used": [], "cache_hit": True}
    except Exception as e:
        logger.warning("Cache check failed: %s", e)

    # RAG Pipeline
    expander = HyDEExpander()
    expanded_query = await expander.expand_query(request.message)

    hybrid_search = get_hybrid_search()
    top_candidates = hybrid_search.search(expanded_query, k=settings.HYBRID_SEARCH_K)

    reranker = get_reranker()
    top_chunks = await reranker.arerank(
        request.message, top_candidates, top_k=settings.RERANKER_TOP_K
    )

    builder = ContextBuilder()
    system_prompt = builder.build_system_prompt(top_chunks)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": request.message},
    ]

    try:
        if openai_client:
            response = await openai_client.chat.completions.create(
                model=settings.LLM_MODEL_NAME,
                messages=messages,
                stream=False,
                max_tokens=settings.LLM_MAX_TOKENS,
            )
            answer = response.choices[0].message.content
        elif hf_client:
            response = await hf_client.chat_completion(
                model=settings.LLM_MODEL_NAME,
                messages=messages,
                stream=False,
                max_tokens=settings.LLM_MAX_TOKENS,
            )
            answer = response.choices[0].message.content
        else:
            raise HTTPException(status_code=503, detail="No LLM provider available")

        # Store in cache
        try:
            cache = get_semantic_cache()
            cache.store_cache(request.message, answer)
        except Exception as e:
            logger.warning("Failed to store in cache: %s", e)

        return {
            "answer": answer,
            "context_used": [c.get("id") for c in top_chunks],
            "cache_hit": False,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("LLM query error: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail=f"LLM provider error: {str(e)}")


@router.post("/{message_id}/feedback")
async def submit_feedback(
    message_id: str, request: FeedbackRequest, db: DbSessionOrm = Depends(get_db)
):
    """Records human feedback (thumbs up/down) for a specific message."""
    msg = (
        db.query(ConversationHistory)
        .filter(ConversationHistory.id == message_id)
        .first()
    )
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    # Check for duplicate feedback
    existing = (
        db.query(HumanFeedback)
        .filter(HumanFeedback.message_id == msg.id)
        .first()
    )
    if existing:
        existing.vote = request.vote
        existing.comment = request.comment
        db.commit()
        return {"status": "updated", "message_id": message_id}

    feedback = HumanFeedback(
        message_id=msg.id,
        vote=request.vote,
        comment=request.comment,
    )
    db.add(feedback)
    db.commit()

    logger.info("Feedback recorded for message %s: vote=%d", message_id, request.vote)
    return {"status": "recorded", "message_id": message_id}
