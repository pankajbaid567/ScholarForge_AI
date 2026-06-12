import os
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_recall
from datasets import Dataset

class RagasEvaluator:
    def __init__(self):
        # We need an LLM for evaluation, Ragas uses OpenAI by default
        # Ensure OPENAI_API_KEY is in the environment
        self.metrics = [
            faithfulness,
            answer_relevancy,
            context_recall
        ]

    def evaluate_single_interaction(self, question: str, answer: str, contexts: list[str], ground_truth: str = None) -> dict:
        """
        Evaluates a single RAG generation. 
        Note: Context Recall requires a ground_truth answer. If none is provided, it will be skipped.
        """
        data = {
            "question": [question],
            "answer": [answer],
            "contexts": [contexts],
        }
        
        metrics_to_run = [faithfulness, answer_relevancy]
        
        if ground_truth:
            data["ground_truth"] = [ground_truth]
            metrics_to_run.append(context_recall)
            
        dataset = Dataset.from_dict(data)
        
        try:
            result = evaluate(dataset, metrics=metrics_to_run)
            return {
                "faithfulness": result.get('faithfulness', 0.0),
                "answer_relevancy": result.get('answer_relevancy', 0.0),
                "context_recall": result.get('context_recall', 0.0) if ground_truth else None
            }
        except Exception as e:
            print(f"Error during RAGAS evaluation: {e}")
            return {}
