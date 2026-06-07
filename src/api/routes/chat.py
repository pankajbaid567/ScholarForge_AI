from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
import asyncio
from sqlalchemy.orm import Session
from openai import AsyncOpenAI
import time

from src.database.session import get_db
from src.database.models import Session as DbSession, ConversationHistory, MessageRole, HumanFeedback
from src.generation.context_builder import ContextBuilder
from src.generation.memory import MemoryManager
from src.api.dependencies import get_hybrid_search, get_reranker
from src.core.config import get_settings
from src.workers.celery_app import task_run_ragas
from src.retrieval.semantic_cache import get_semantic_cache
from src.retrieval.hyde import HyDEExpander

router = APIRouter()
settings = get_settings()
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

class ChatRequest(BaseModel):
    session_id: str
    message: str
    stream: bool = True

class FeedbackRequest(BaseModel):
    vote: int
    comment: str = None

async def llm_stream(prompt: str, history: list, top_5_chunks: list, start_time: float, message_id: str, request_msg: str):
    """
    Real streaming generator interacting with OpenAI.
    """
    messages = [{"role": "system", "content": prompt}] + history
    
    full_response = ""
    try:
        stream = await openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            stream=True
        )
        
        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                full_response += content
                yield f"data: {json.dumps({'delta': content})}\n\n"
                
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        return

    # Calculate latency
    latency_ms = int((time.time() - start_time) * 1000)
    
    # Send final metadata block
    context_list = [c.get('text', '') for c in top_5_chunks]
    metadata = {
        "latency_ms": latency_ms,
        "context_chunks": [c.get('id', 'unknown') for c in top_5_chunks],
        "cache_hit": False
    }
    yield f"data: {json.dumps({'metadata': metadata})}\n\n"
    
    # Store in Semantic Cache
    cache = get_semantic_cache()
    cache.store_cache(request_msg, full_response)
    
    # Dispatch to Celery background evaluation worker
    task_run_ragas.delay(
        str(message_id), 
        request_msg, 
        full_response, 
        context_list
    )

@router.post("/stream")
async def chat_stream(request: ChatRequest, db: Session = Depends(get_db)):
    start_time = time.time()
    
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured.")

    # 1. Session Management
    session = db.query(DbSession).filter(DbSession.id == request.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 1.5 Semantic Cache Check
    cache = get_semantic_cache()
    cached_response = cache.check_cache(request.message)
    if cached_response:
        # Save User Message
        user_msg = ConversationHistory(session_id=session.id, role=MessageRole.USER, content=request.message)
        db.add(user_msg)
        
        # Save Assistant Message
        assistant_msg = ConversationHistory(session_id=session.id, role=MessageRole.ASSISTANT, content=cached_response, context_used=[])
        db.add(assistant_msg)
        db.commit()
        
        # Stream the cached response instantly
        async def cached_stream():
            latency_ms = int((time.time() - start_time) * 1000)
            yield f"data: {json.dumps({'delta': cached_response})}\n\n"
            metadata = {"latency_ms": latency_ms, "context_chunks": [], "cache_hit": True}
            yield f"data: {json.dumps({'metadata': metadata})}\n\n"
            
        return StreamingResponse(cached_stream(), media_type="text/event-stream")

    # Save User Message
    user_msg = ConversationHistory(session_id=session.id, role=MessageRole.USER, content=request.message)
    db.add(user_msg)
    db.commit()

    # 2. Fetch History
    db_history = db.query(ConversationHistory).filter(ConversationHistory.session_id == session.id).order_by(ConversationHistory.created_at.asc()).all()
    memory_manager = MemoryManager()
    formatted_history = memory_manager.format_history(db_history)
    
    # 2.5 Query Expansion (HyDE)
    expander = HyDEExpander()
    expanded_query = await expander.expand_query(request.message)
    
    # 3. Hybrid Search
    hybrid_search = get_hybrid_search()
    top_20_chunks = hybrid_search.search(expanded_query, k=20)
    
    # 4. Reranking
    reranker = get_reranker()
    top_5_chunks = reranker.rerank(request.message, top_20_chunks, top_k=5)
    
    # 5. Context Builder
    builder = ContextBuilder()
    system_prompt = builder.build_system_prompt(top_5_chunks)
    
    # Pre-create Assistant Message record to link Evaluation
    context_ids = [c.get('id', 'unknown') for c in top_5_chunks]
    assistant_msg = ConversationHistory(
        session_id=session.id, 
        role=MessageRole.ASSISTANT, 
        content="", # Will be updated later or kept empty for streaming brevity in MVP
        context_used=context_ids
    )
    db.add(assistant_msg)
    db.commit()
    
    # 6. Stream response
    return StreamingResponse(
        llm_stream(system_prompt, formatted_history, top_5_chunks, start_time, str(assistant_msg.id), request.message), 
        media_type="text/event-stream"
    )

@router.post("/query")
async def simple_query(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Synchronous, non-streaming query endpoint.
    """
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured.")
        
    cache = get_semantic_cache()
    cached_response = cache.check_cache(request.message)
    if cached_response:
        return {
            "answer": cached_response,
            "context_used": [],
            "cache_hit": True
        }
        
    expander = HyDEExpander()
    expanded_query = await expander.expand_query(request.message)
        
    hybrid_search = get_hybrid_search()
    top_20_chunks = hybrid_search.search(expanded_query, k=20)
    
    reranker = get_reranker()
    top_5_chunks = reranker.rerank(request.message, top_20_chunks, top_k=5)
    
    builder = ContextBuilder()
    system_prompt = builder.build_system_prompt(top_5_chunks)
    
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": request.message}]
    
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            stream=False
        )
        answer = response.choices[0].message.content
        
        # Store in cache
        cache.store_cache(request.message, answer)
        
        return {
            "answer": answer,
            "context_used": [c.get('id') for c in top_5_chunks],
            "cache_hit": False
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{message_id}/feedback")
async def submit_feedback(message_id: str, request: FeedbackRequest, db: Session = Depends(get_db)):
    msg = db.query(ConversationHistory).filter(ConversationHistory.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
        
    feedback = HumanFeedback(
        message_id=msg.id,
        vote=request.vote,
        comment=request.comment
    )
    db.add(feedback)
    db.commit()
    
    return {"status": "recorded", "message_id": message_id}
