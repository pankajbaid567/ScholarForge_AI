"""
ChromaDB Vector Store for dense retrieval.

Uses persistent ChromaDB with local ONNX embeddings (all-MiniLM-L6-v2)
by default, falling back to OpenAI embeddings if an API key is configured.
"""
import logging
import os

import chromadb
import chromadb.utils.embedding_functions as embedding_functions

from src.core.config import get_settings

logger = logging.getLogger("scholarforge.retrieval.vector_store")
settings = get_settings()


class VectorStore:
    def __init__(self, collection_name: str = "scholarforge_docs"):
        db_path = settings.CHROMA_DB_DIR

        # Initialize ChromaDB client (Cloud, HTTP, or Persistent)
        if settings.CHROMA_TENANT and settings.CHROMA_DATABASE:
            logger.info("Connecting to Chroma Cloud (tenant: %s, db: %s)", settings.CHROMA_TENANT, settings.CHROMA_DATABASE)
            self.client = chromadb.CloudClient(
                tenant=settings.CHROMA_TENANT,
                database=settings.CHROMA_DATABASE,
                api_key=settings.CHROMA_API_KEY,
            )
        elif settings.CHROMA_HOST:
            logger.info("Connecting to remote ChromaDB at %s:%d", settings.CHROMA_HOST, settings.CHROMA_PORT)
            self.client = chromadb.HttpClient(
                host=settings.CHROMA_HOST, 
                port=settings.CHROMA_PORT
            )
        else:
            logger.info("Using local persistent ChromaDB at %s", db_path)
            self.client = chromadb.PersistentClient(path=db_path)

        # Switchable Providers logic
        if settings.OPENAI_API_KEY:
            logger.info("Using OpenAI embeddings for vector store")
            emb_fn = embedding_functions.OpenAIEmbeddingFunction(
                api_key=settings.OPENAI_API_KEY,
                model_name="text-embedding-3-small",
            )
        else:
            # Default local embeddings (ONNX all-MiniLM-L6-v2)
            logger.info("Using local ONNX embeddings (%s)", settings.EMBEDDING_MODEL_NAME)
            emb_fn = embedding_functions.DefaultEmbeddingFunction()

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=emb_fn,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "Vector store initialized: collection='%s', count=%d",
            collection_name,
            self.collection.count(),
        )

    def add_chunks(self, chunks: list[dict], batch_size: int = 50) -> None:
        """
        Adds document chunks to the ChromaDB collection in batches.
        Batching prevents OOM on large documents while keeping each
        batch efficient (one embedding call per batch).
        
        Expected chunk format: { 'id': str, 'text': str, 'metadata': dict }
        """
        if not chunks:
            logger.warning("add_chunks called with empty list; skipping")
            return

        total = len(chunks)
        added = 0

        try:
            for i in range(0, total, batch_size):
                batch = chunks[i : i + batch_size]
                ids = [chunk["id"] for chunk in batch]
                documents = [chunk["text"] for chunk in batch]
                metadatas = [chunk.get("metadata", {}) for chunk in batch]

                self.collection.add(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids,
                )
                added += len(batch)
                logger.info(
                    "ChromaDB batch %d/%d: added %d chunks (%d/%d total)",
                    (i // batch_size) + 1,
                    (total + batch_size - 1) // batch_size,
                    len(batch),
                    added,
                    total,
                )

            logger.info("Successfully added all %d chunks to ChromaDB", total)
        except Exception as e:
            logger.error(
                "Failed to add chunks to ChromaDB (added %d/%d before failure): %s",
                added, total, e, exc_info=True,
            )
            raise

    def search(self, query: str, k: int = 20) -> list[dict]:
        """
        Performs a dense vector search.
        Returns results sorted by cosine distance (lower = more similar).
        """
        try:
            # Clamp k to collection size to avoid ChromaDB warning
            collection_count = self.collection.count()
            effective_k = min(k, collection_count) if collection_count > 0 else 1

            if collection_count == 0:
                logger.debug("Vector store is empty; returning no results")
                return []

            results = self.collection.query(
                query_texts=[query],
                n_results=effective_k,
            )

            # Format the output to a standard list of dictionaries
            formatted_results = []
            if results and results["ids"] and results["ids"][0]:
                for i in range(len(results["ids"][0])):
                    formatted_results.append({
                        "id": results["ids"][0][i],
                        "text": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "score": results["distances"][0][i],  # Cosine distance
                    })

            logger.debug("Dense search returned %d results", len(formatted_results))
            return formatted_results

        except Exception as e:
            logger.error("Vector search failed: %s", e, exc_info=True)
            return []
