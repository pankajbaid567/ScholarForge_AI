import chromadb
from chromadb.config import Settings
import chromadb.utils.embedding_functions as embedding_functions
from src.core.config import get_settings
import os

class VectorStore:
    def __init__(self, collection_name: str = "scholarforge_docs"):
        db_path = os.getenv("CHROMA_DB_DIR", "./chroma_data")
        # Initialize persistent ChromaDB client
        self.client = chromadb.PersistentClient(path=db_path)
        
        app_settings = get_settings()
        
        # Switchable Providers logic
        if app_settings.OPENAI_API_KEY:
            emb_fn = embedding_functions.OpenAIEmbeddingFunction(
                api_key=app_settings.OPENAI_API_KEY,
                model_name="text-embedding-3-small"
            )
        else:
            # Fallback to default
            emb_fn = embedding_functions.DefaultEmbeddingFunction()

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=emb_fn,
            metadata={"hnsw:space": "cosine"}
        )

    def add_chunks(self, chunks: list[dict]):
        """
        Adds document chunks to the ChromaDB collection.
        Expected chunk format: { 'id': str, 'text': str, 'metadata': dict }
        """
        if not chunks:
            return

        ids = [chunk['id'] for chunk in chunks]
        documents = [chunk['text'] for chunk in chunks]
        metadatas = [chunk.get('metadata', {}) for chunk in chunks]

        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

    def search(self, query: str, k: int = 20) -> list[dict]:
        """
        Performs a dense vector search.
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=k
        )
        
        # Format the output to a standard list of dictionaries
        formatted_results = []
        if results and results['ids'] and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                formatted_results.append({
                    "id": results['ids'][0][i],
                    "text": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "score": results['distances'][0][i] # Cosine distance
                })
                
        return formatted_results
