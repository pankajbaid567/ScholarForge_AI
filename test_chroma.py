from src.retrieval.vector_store import VectorStore
import uuid
store = VectorStore()
store.add_chunks([{"id": str(uuid.uuid4()), "text": "This is a test chunk", "metadata": {"test": True}}])
print("Success:", store.collection.count())
