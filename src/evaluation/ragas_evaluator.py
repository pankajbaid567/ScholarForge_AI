"""
RAGAS Evaluation Engine.

Evaluates RAG pipeline quality using LLM-as-a-judge metrics:
  - Faithfulness: Does the answer stick to the retrieved context?
  - Answer Relevancy: Is the answer relevant to the question?
  - Context Recall: Was all necessary context retrieved?

Uses a custom LangChain LLM wrapper to work with Hugging Face
Inference API's modern chat_completion() method, bypassing
deprecated/broken endpoints in older library versions.
"""
import logging
from typing import Any, List, Optional

from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_recall
from datasets import Dataset
from langchain_core.language_models.llms import LLM
from langchain_core.callbacks.manager import (
    CallbackManagerForLLMRun,
    AsyncCallbackManagerForLLMRun,
)
from huggingface_hub import AsyncInferenceClient, InferenceClient

from src.core.config import get_settings

logger = logging.getLogger("scholarforge.evaluation.ragas")
settings = get_settings()


class CustomHuggingFaceLLM(LLM):
    """
    Custom LangChain LLM wrapper for Hugging Face Inference API.

    Uses the modern chat_completion() method instead of the deprecated
    post() method that was removed in newer huggingface_hub versions.
    """

    sync_client: Any = None
    async_client: Any = None
    model_name: str = ""

    def __init__(self, token: str, model_name: str = None):
        super().__init__()
        self.model_name = model_name or settings.LLM_MODEL_NAME
        self.sync_client = InferenceClient(token=token)
        self.async_client = AsyncInferenceClient(token=token)
        logger.info("CustomHuggingFaceLLM initialized with model: %s", self.model_name)

    @property
    def _llm_type(self) -> str:
        return "custom_huggingface"

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        messages = [{"role": "user", "content": prompt}]
        try:
            response = self.sync_client.chat_completion(
                model=self.model_name,
                messages=messages,
                max_tokens=settings.LLM_MAX_TOKENS,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error("HuggingFace LLM call failed: %s", e)
            return f"Error: {e}"

    async def _acall(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        messages = [{"role": "user", "content": prompt}]
        try:
            response = await self.async_client.chat_completion(
                model=self.model_name,
                messages=messages,
                max_tokens=settings.LLM_MAX_TOKENS,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error("HuggingFace async LLM call failed: %s", e)
            return f"Error: {e}"


class RagasEvaluator:
    """Evaluates RAG pipeline quality using RAGAS metrics."""

    def __init__(self):
        self.metrics = [faithfulness, answer_relevancy, context_recall]
        self.llm = None
        self.embeddings = None

        if not settings.OPENAI_API_KEY and settings.HUGGINGFACE_API_KEY:
            try:
                from langchain_huggingface import HuggingFaceEmbeddings

                self.llm = CustomHuggingFaceLLM(
                    token=settings.HUGGINGFACE_API_KEY,
                    model_name=settings.LLM_MODEL_NAME,
                )
                self.embeddings = HuggingFaceEmbeddings(
                    model_name=settings.EMBEDDING_MODEL_NAME,
                )
                logger.info("RAGAS evaluator initialized with HuggingFace backend")
            except Exception as e:
                logger.error("Failed to initialize RAGAS evaluator: %s", e)

    def evaluate_single_interaction(
        self,
        question: str,
        answer: str,
        contexts: list[str],
        ground_truth: str = None,
    ) -> dict:
        """
        Evaluates a single RAG generation.
        Note: Context Recall requires a ground_truth answer.
        If none is provided, it will be skipped.
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
            kwargs = {}
            if self.llm and self.embeddings:
                kwargs["llm"] = self.llm
                kwargs["embeddings"] = self.embeddings

            result = evaluate(dataset, metrics=metrics_to_run, **kwargs)

            evaluation_result = {
                "faithfulness": result.get("faithfulness", 0.0),
                "answer_relevancy": result.get("answer_relevancy", 0.0),
                "context_recall": (
                    result.get("context_recall", 0.0) if ground_truth else None
                ),
            }

            logger.info(
                "RAGAS evaluation: faithfulness=%.3f, relevancy=%.3f",
                evaluation_result["faithfulness"],
                evaluation_result["answer_relevancy"],
            )
            return evaluation_result

        except Exception as e:
            logger.error("RAGAS evaluation failed: %s", e, exc_info=True)
            return {}
