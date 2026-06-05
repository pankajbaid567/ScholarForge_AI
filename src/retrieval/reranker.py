from sentence_transformers import CrossEncoder
from typing import List, Dict

class CrossEncoderReranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        """
        Initializes the Cross-Encoder. 
        ms-marco-MiniLM-L-6-v2 is fast and effective.
        For absolute highest accuracy (at the cost of latency), use 'BAAI/bge-reranker-large'.
        """
        self.model = CrossEncoder(model_name, max_length=512)

    def rerank(self, query: str, candidates: List[Dict], top_k: int = 5) -> List[Dict]:
        """
        Reranks a list of candidate chunks against the query.
        
        Args:
            query: The user's search query.
            candidates: List of dictionaries containing at least an 'id' and 'text'.
            top_k: Number of absolute top results to return.
            
        Returns:
            List of the top_k candidates, sorted by cross-encoder score.
        """
        if not candidates:
            return []

        # The CrossEncoder expects input as a list of pairs: [[query, text1], [query, text2], ...]
        sentence_pairs = [[query, candidate['text']] for candidate in candidates]
        
        # Predict logits
        scores = self.model.predict(sentence_pairs)
        
        # Attach scores back to candidates
        for i, candidate in enumerate(candidates):
            candidate['rerank_score'] = float(scores[i])
            
        # Sort by rerank score descending
        reranked = sorted(candidates, key=lambda x: x['rerank_score'], reverse=True)
        
        return reranked[:top_k]
