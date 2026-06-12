from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import List, Dict

class DocumentChunker:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ".", " ", ""]
        )

    def chunk_document(self, text: str, document_id: str, metadata: dict = None) -> List[Dict]:
        """
        Splits a document text into smaller chunks and attaches metadata.
        """
        if metadata is None:
            metadata = {}
            
        chunks = self.splitter.split_text(text)
        
        results = []
        for index, chunk in enumerate(chunks):
            chunk_data = {
                "document_id": document_id,
                "chunk_index": index,
                "text": chunk,
                "token_count": len(chunk.split()), # Approximate token count
                "metadata": metadata.copy()
            }
            results.append(chunk_data)
            
        return results
