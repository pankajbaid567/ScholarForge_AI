"""
Document management API routes.

Handles:
  - Single file upload with deduplication
  - Bulk file upload
  - Document listing
  - Document deletion

Security:
  - Filename sanitization to prevent path traversal
  - File size limits
  - Extension validation
"""
import hashlib
import logging
import os
import re
import uuid

from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List

from src.database.session import get_db
from src.database.models import Document, Chunk, DocumentStatus
from src.workers.celery_app import task_run_ingestion
from src.core.config import get_settings

logger = logging.getLogger("scholarforge.api.documents")
settings = get_settings()
router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".html"}
MAX_UPLOAD_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


def _sanitize_filename(filename: str) -> str:
    """
    Sanitizes a filename to prevent path traversal attacks.
    Strips directory components and special characters.
    """
    # Remove any directory components
    filename = os.path.basename(filename)
    # Remove any characters that aren't alphanumeric, dots, hyphens, or underscores
    filename = re.sub(r'[^\w.\-]', '_', filename)
    # Collapse multiple underscores
    filename = re.sub(r'_+', '_', filename)
    return filename or "unnamed_document"


def _validate_file(filename: str, file_bytes: bytes) -> None:
    """Validates file extension and size."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(file_bytes) / (1024*1024):.1f}MB). Max: {settings.MAX_UPLOAD_SIZE_MB}MB",
        )
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")


@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload and index a single document."""
    safe_filename = _sanitize_filename(file.filename)
    file_bytes = await file.read()

    _validate_file(safe_filename, file_bytes)

    content_hash = hashlib.sha256(file_bytes).hexdigest()

    # Check deduplication
    existing = db.query(Document).filter(Document.content_hash == content_hash).first()
    if existing:
        logger.info("Duplicate document detected: %s (hash=%s)", safe_filename, content_hash[:12])
        return {"document_id": str(existing.id), "status": "already_exists"}

    doc_id = uuid.uuid4()

    new_doc = Document(
        id=doc_id,
        filename=safe_filename,
        content_hash=content_hash,
        status=DocumentStatus.PENDING,
    )
    db.add(new_doc)
    db.commit()

    # Dispatch ingestion to Celery
    task_run_ingestion.apply_async(
        args=[file_bytes.hex(), safe_filename, str(doc_id)],
        queue="ingestion",
    )

    logger.info("Document queued for ingestion: %s (doc_id=%s)", safe_filename, doc_id)

    return {
        "document_id": str(doc_id),
        "filename": safe_filename,
        "status": "processing",
        "job_url": f"/api/v1/documents/jobs/{doc_id}",
    }


@router.post("/bulk")
async def upload_documents_bulk(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Upload and index multiple documents at once."""
    job_ids = []
    skipped = []

    for file in files:
        safe_filename = _sanitize_filename(file.filename)
        file_bytes = await file.read()

        # Validate each file
        ext = os.path.splitext(safe_filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            skipped.append({"filename": safe_filename, "reason": "unsupported_format"})
            continue
        if len(file_bytes) > MAX_UPLOAD_BYTES:
            skipped.append({"filename": safe_filename, "reason": "too_large"})
            continue
        if len(file_bytes) == 0:
            skipped.append({"filename": safe_filename, "reason": "empty_file"})
            continue

        content_hash = hashlib.sha256(file_bytes).hexdigest()

        existing = db.query(Document).filter(Document.content_hash == content_hash).first()
        if existing:
            job_ids.append(str(existing.id))
            continue

        doc_id = uuid.uuid4()
        new_doc = Document(
            id=doc_id,
            filename=safe_filename,
            content_hash=content_hash,
            status=DocumentStatus.PENDING,
        )
        db.add(new_doc)
        db.commit()

        job_ids.append(str(doc_id))
        task_run_ingestion.apply_async(
            args=[file_bytes.hex(), safe_filename, str(doc_id)],
            queue="ingestion",
        )

    logger.info("Bulk upload: %d queued, %d skipped", len(job_ids), len(skipped))

    return {
        "job_ids": job_ids,
        "skipped": skipped,
        "status": "processing",
    }


@router.get("/")
async def get_documents(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List all indexed documents."""
    docs = db.query(Document).offset(skip).limit(limit).all()
    return [
        {
            "id": str(doc.id),
            "filename": doc.filename,
            "status": doc.status.value if doc.status else "UNKNOWN",
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
        }
        for doc in docs
    ]


@router.get("/status/{doc_id}")
async def get_document_status(doc_id: str, db: Session = Depends(get_db)):
    """
    Returns the current indexing status of a single document.
    Used by the frontend to poll for completion.
    """
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    chunk_count = db.query(Chunk).filter(Chunk.document_id == doc_id).count()

    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "status": doc.status.value if doc.status else "UNKNOWN",
        "chunk_count": chunk_count,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


@router.post("/status/bulk")
async def get_documents_status_bulk(
    doc_ids: List[str],
    db: Session = Depends(get_db),
):
    """
    Returns the current indexing status of multiple documents.
    Used by the frontend to poll for batch upload completion.
    """
    results = []
    for doc_id in doc_ids:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            chunk_count = db.query(Chunk).filter(Chunk.document_id == doc_id).count()
            results.append({
                "id": str(doc.id),
                "filename": doc.filename,
                "status": doc.status.value if doc.status else "UNKNOWN",
                "chunk_count": chunk_count,
            })
    return results


@router.delete("/{doc_id}")
async def delete_document(doc_id: str, db: Session = Depends(get_db)):
    """Delete a document and its associated chunks."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    db.delete(doc)
    db.commit()

    logger.info("Document deleted: %s", doc_id)

    # Note: ChromaDB vectors should be purged here in a production system.
    # For now, the orphaned vectors will simply not match any DB chunks.
    return {"status": "deleted", "document_id": doc_id}
