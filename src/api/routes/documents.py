from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
import uuid
import hashlib

from src.database.session import get_db
from src.database.models import Document, DocumentStatus
from src.workers.celery_app import task_run_ingestion

router = APIRouter()

@router.post("/upload")
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db)):
    # Basic validation
    if not file.filename.endswith(('.pdf', '.txt', '.md', '.html')):
        raise HTTPException(status_code=400, detail="Unsupported file format")

    file_bytes = await file.read()
    content_hash = hashlib.sha256(file_bytes).hexdigest()
    
    # Check deduplication
    existing = db.query(Document).filter(Document.content_hash == content_hash).first()
    if existing:
        return {"document_id": str(existing.id), "status": "already_exists"}

    doc_id = uuid.uuid4()
    
    new_doc = Document(
        id=doc_id,
        filename=file.filename,
        content_hash=content_hash,
        status=DocumentStatus.PENDING
    )
    db.add(new_doc)
    db.commit()
    
    # Kick off background indexing via Celery
    task_run_ingestion.delay(file_bytes.hex(), file.filename, str(doc_id))
    
    return {
        "document_id": str(doc_id),
        "filename": file.filename,
        "status": "processing",
        "job_url": f"/api/v1/documents/jobs/{doc_id}"
    }

@router.post("/bulk")
async def upload_documents_bulk(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    job_ids = []
    for file in files:
        if not file.filename.endswith(('.pdf', '.txt', '.md', '.html')):
            continue # Skip invalid files
            
        file_bytes = await file.read()
        content_hash = hashlib.sha256(file_bytes).hexdigest()
        
        existing = db.query(Document).filter(Document.content_hash == content_hash).first()
        if existing:
            job_ids.append(str(existing.id))
            continue
            
        doc_id = uuid.uuid4()
        new_doc = Document(
            id=doc_id,
            filename=file.filename,
            content_hash=content_hash,
            status=DocumentStatus.PENDING
        )
        db.add(new_doc)
        db.commit()
        
        job_ids.append(str(doc_id))
        task_run_ingestion.delay(file_bytes.hex(), file.filename, str(doc_id))

    return {
        "job_ids": job_ids,
        "status": "processing"
    }

@router.get("/")
async def get_documents(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    docs = db.query(Document).offset(skip).limit(limit).all()
    return docs

@router.delete("/{doc_id}")
async def delete_document(doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    db.delete(doc)
    db.commit()
    # Note: ChromaDB vectors and BM25 index should ideally be updated here too.
    # In a full production system, we'd fire off a background task to purge the vector store.
    return {"status": "deleted", "document_id": doc_id}
