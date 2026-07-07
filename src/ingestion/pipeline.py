"""
Document Ingestion Pipeline.

Orchestrates the full ingestion flow:
  1. Parse document (PDF, TXT, MD, HTML)
  2. Chunk into overlapping segments
  3. Persist chunks to PostgreSQL
  4. Embed and index in ChromaDB (dense vector store)

Note: BM25 (sparse) index is lazily loaded from PostgreSQL by the
SparseStore on search, so we no longer need to rebuild it here.
This solves the Celery/FastAPI process isolation bug.
"""
import logging
import traceback
import uuid

from src.ingestion.parsers import ParserFactory
from src.ingestion.chunker import DocumentChunker
from src.api.dependencies import get_vector_store
from src.database.session import SessionLocal
from src.database.models import Document, Chunk, DocumentStatus
from src.core.config import get_settings

logger = logging.getLogger("scholarforge.ingestion.pipeline")
settings = get_settings()


def run_ingestion(file_bytes: bytes, filename: str, doc_id: str) -> None:
    """
    Runs the full ingestion pipeline for a single document.

    Args:
        file_bytes: Raw file content as bytes.
        filename: Original filename (used for parser selection).
        doc_id: UUID of the Document record in PostgreSQL.
    """
    db = SessionLocal()
    try:
        # 1. Update status to INDEXING
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc:
            logger.error("Document %s not found in database; aborting ingestion", doc_id)
            return

        doc.status = DocumentStatus.INDEXING
        db.commit()
        logger.info("Starting ingestion for '%s' (doc_id=%s, %d bytes)", filename, doc_id, len(file_bytes))

        # 2. Parse
        parser = ParserFactory.get_parser(filename)
        text = parser.parse(file_content=file_bytes)

        if not text or not text.strip():
            logger.warning("Parser returned empty text for '%s'; marking as FAILED", filename)
            doc.status = DocumentStatus.FAILED
            db.commit()
            return

        logger.info("Parsed '%s': %d characters extracted", filename, len(text))

        # 3. Chunk
        chunker = DocumentChunker(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )
        chunks = chunker.chunk_document(
            text=text,
            document_id=str(doc_id),
            metadata={"filename": filename},
        )
        logger.info("Chunked '%s' into %d segments", filename, len(chunks))

        # 4. Save chunks to PostgreSQL (bulk insert for performance)
        db_chunks = []
        for c in chunks:
            chunk_id = uuid.uuid4()
            db_chunks.append(Chunk(
                id=chunk_id,
                document_id=doc_id,
                chunk_index=c["chunk_index"],
                text=c["text"],
                token_count=c["token_count"],
                metadata_=c["metadata"],
            ))
            # Assign the UUID string ID for the vector store
            c["id"] = str(chunk_id)

        db.bulk_save_objects(db_chunks)
        db.commit()
        logger.info("Saved %d chunks to PostgreSQL for doc %s", len(chunks), doc_id)

        # 5. Embed & Index in ChromaDB (dense vector store)
        v_store = get_vector_store()
        v_store.add_chunks(chunks)
        logger.info("Indexed %d chunks in ChromaDB for doc %s", len(chunks), doc_id)

        # Note: BM25 sparse index is lazily loaded from PostgreSQL by
        # SparseStore.search(), so we do NOT rebuild it here. This is
        # intentional — it solves the Celery/FastAPI process isolation bug
        # where the Celery worker's in-memory BM25 was invisible to FastAPI.

        # 6. Mark as INDEXED
        doc.status = DocumentStatus.INDEXED
        db.commit()
        logger.info("Ingestion complete for '%s' (doc_id=%s)", filename, doc_id)

    except Exception as e:
        logger.error(
            "Ingestion failed for '%s' (doc_id=%s): %s\n%s",
            filename,
            doc_id,
            e,
            traceback.format_exc(),
        )
        try:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if doc:
                doc.status = DocumentStatus.FAILED
                db.commit()
        except Exception as db_err:
            logger.error("Failed to update document status to FAILED: %s", db_err)
    finally:
        db.close()
