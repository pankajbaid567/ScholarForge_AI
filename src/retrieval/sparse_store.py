from rank_bm25 import BM25Okapi
import re
from typing import List, Dict

class SparseStore:
    def __init__(self):
        self.corpus: List[Dict] = []
        self.tokenized_corpus: List[List[str]] = []
        self.bm25 = None

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenizer: lowercase and split by non-alphanumeric characters."""
        return [word for word in re.split(r'\W+', text.lower()) if word]

    def build_index(self, chunks: List[Dict]):
        """
        Builds the BM25 index from a list of chunk dictionaries.
        Expected format: {'id': str, 'text': str, 'metadata': dict}
        """
        self.corpus = chunks
        self.tokenized_corpus = [self._tokenize(chunk['text']) for chunk in chunks]
        
        if self.tokenized_corpus:
            self.bm25 = BM25Okapi(self.tokenized_corpus)

    def search(self, query: str, k: int = 20) -> List[Dict]:
        """
        Performs a sparse (keyword) search using BM25.
        """
        if not self.bm25:
            return []

        tokenized_query = self._tokenize(query)
        # Get raw BM25 scores for all documents
        scores = self.bm25.get_scores(tokenized_query)
        
        # Pair scores with the corpus
        results = [{"chunk": self.corpus[i], "score": scores[i]} for i in range(len(self.corpus))]
        
        # Sort by score descending
        results = sorted(results, key=lambda x: x["score"], reverse=True)
        
        # Return top k, formatting similarly to vector store output
        formatted_results = []
        for res in results[:k]:
            if res["score"] > 0: # Only return documents that actually matched something
                formatted_results.append({
                    "id": res["chunk"]["id"],
                    "text": res["chunk"]["text"],
                    "metadata": res["chunk"].get("metadata", {}),
                    "score": res["score"] # Raw BM25 score
                })
                
        return formatted_results
