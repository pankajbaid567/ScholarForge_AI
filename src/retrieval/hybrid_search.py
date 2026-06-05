from typing import List, Dict

class HybridSearch:
    def __init__(self, vector_store, sparse_store):
        self.vector_store = vector_store
        self.sparse_store = sparse_store

    def search(self, query: str, k: int = 20, c: int = 60, alpha: float = 0.5) -> List[Dict]:
        """
        Performs Reciprocal Rank Fusion (RRF) on results from Dense and Sparse stores.
        
        RRF_Score = (alpha * (1 / (c + rank_dense))) + ((1 - alpha) * (1 / (c + rank_sparse)))
        
        Args:
            query: The search string.
            k: Number of total candidates to retrieve per store and return.
            c: RRF smoothing constant (usually 60).
            alpha: Weight for dense vs sparse. 0.5 means equal weight.
        """
        # Execute searches independently
        # Note: In production, these should be executed concurrently via asyncio
        dense_results = self.vector_store.search(query, k=k)
        sparse_results = self.sparse_store.search(query, k=k)

        # Dictionary to accumulate RRF scores by chunk ID
        # Format: { id: { 'chunk_data': dict, 'rrf_score': float } }
        fusion_map = {}

        # Process Dense Results
        for rank, res in enumerate(dense_results):
            doc_id = res['id']
            if doc_id not in fusion_map:
                fusion_map[doc_id] = {'chunk_data': res, 'rrf_score': 0.0}
            
            # 1-indexed rank
            rank_score = 1.0 / (c + (rank + 1))
            fusion_map[doc_id]['rrf_score'] += alpha * rank_score

        # Process Sparse Results
        for rank, res in enumerate(sparse_results):
            doc_id = res['id']
            if doc_id not in fusion_map:
                fusion_map[doc_id] = {'chunk_data': res, 'rrf_score': 0.0}
            
            # 1-indexed rank
            rank_score = 1.0 / (c + (rank + 1))
            fusion_map[doc_id]['rrf_score'] += (1.0 - alpha) * rank_score

        # Convert back to list and sort by RRF score descending
        fused_results = [
            {**data['chunk_data'], 'score': data['rrf_score']} 
            for data in fusion_map.values()
        ]
        
        fused_results = sorted(fused_results, key=lambda x: x['score'], reverse=True)

        return fused_results[:k]
