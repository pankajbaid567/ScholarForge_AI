from src.ingestion.parsers import ParserFactory
from src.ingestion.chunker import DocumentChunker
from src.api.dependencies import get_vector_store, get_sparse_store
from src.database.session import SessionLocal
from src.database.models import Document, Chunk, DocumentStatus
import os
import uuid

def run_ingestion(file_bytes: bytes, filename: str, doc_id: str):
    db = SessionLocal()
    try:
        # 1. Update status
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.status = DocumentStatus.INDEXING
            db.commit()

        # 2. Parse
        parser = ParserFactory.get_parser(filename)
        text = parser.parse(file_content=file_bytes)
        
        # 3. Chunk
        chunker = DocumentChunker()
        chunks = chunker.chunk_document(text=text, document_id=str(doc_id), metadata={"filename": filename})
        
        # 4. Save chunks to DB
        for c in chunks:
            db_chunk = Chunk(
                document_id=doc_id,
                chunk_index=c['chunk_index'],
                text=c['text'],
                token_count=c['token_count'],
                metadata_=c['metadata']
            )
            db.add(db_chunk)
            # Give the chunk a UUID string ID for the Vector DB
            c['id'] = str(db_chunk.id)
            
        db.commit()
        
        # 5. Embed & Index
        v_store = get_vector_store()
        s_store = get_sparse_store()
        
        # Ensure 'id' exists in all chunks before passing to ChromaDB
        for c in chunks:
            if 'id' not in c:
                c['id'] = str(uuid.uuid4())
                
        v_store.add_chunks(chunks)
        
        # BM25 requires the full corpus for now in this MVP implementation
        all_db_chunks = db.query(Chunk).all()
        corpus = [{"id": str(c.id), "text": c.text, "metadata": c.metadata_} for c in all_db_chunks]
        s_store.build_index(corpus)
        
        # 6. Complete
        if doc:
            doc.status = DocumentStatus.INDEXED
            db.commit()
            
    except Exception as e:
        print(f"Ingestion failed for {doc_id}: {e}")
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc:
            doc.status = DocumentStatus.FAILED
            db.commit()
    finally:
        db.close()
