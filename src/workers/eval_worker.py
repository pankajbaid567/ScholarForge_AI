import asyncio
from src.evaluation.ragas_evaluator import RagasEvaluator
# from src.database.models import Evaluation, ConversationHistory
# from src.database.session import SessionLocal

async def async_evaluation_task(message_id: str, question: str, answer: str, contexts: list[str]):
    """
    Background worker that runs the RAGAS evaluation and saves the result to the DB.
    This ensures that user latency is not impacted by the heavy LLM-as-a-judge calls.
    """
    evaluator = RagasEvaluator()
    
    # Run evaluation
    results = evaluator.evaluate_single_interaction(
        question=question,
        answer=answer,
        contexts=contexts
    )
    
    # Save to database (Mocked for now)
    print(f"Evaluated message {message_id}: {results}")
    
    # db = SessionLocal()
    # try:
    #     new_eval = Evaluation(
    #         message_id=message_id,
    #         faithfulness=results.get('faithfulness'),
    #         answer_rel=results.get('answer_relevancy'),
    #         context_rec=results.get('context_recall')
    #     )
    #     db.add(new_eval)
    #     db.commit()
    # finally:
    #     db.close()
