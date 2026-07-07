"""
Hypothetical Document Embeddings (HyDE) Query Expander.

Uses an LLM to generate a hypothetical academic paragraph answering the
user's question, then combines it with the original query to improve
dense retrieval recall. Falls back gracefully to the raw query if
no LLM is configured or if the expansion call fails.
"""
import asyncio
import logging

from openai import AsyncOpenAI
from huggingface_hub import AsyncInferenceClient

from src.core.config import get_settings

logger = logging.getLogger("scholarforge.retrieval.hyde")
settings = get_settings()


class HyDEExpander:
    def __init__(self):
        self.openai_client = (
            AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            if settings.OPENAI_API_KEY
            else None
        )
        self.hf_client = (
            AsyncInferenceClient(token=settings.HUGGINGFACE_API_KEY)
            if (not settings.OPENAI_API_KEY and settings.HUGGINGFACE_API_KEY)
            else None
        )

    async def expand_query(self, query: str) -> str:
        """
        Uses Hypothetical Document Embeddings (HyDE) to expand a short query
        into a richer academic context paragraph.
        """
        if not self.openai_client and not self.hf_client:
            logger.debug("No LLM client configured; skipping HyDE expansion")
            return query

        prompt = (
            "Please write a short, precise academic paragraph answering the following question. "
            "Use formal academic vocabulary and concepts. Do not include introductory filler. \n\n"
            f"Question: {query}"
        )

        try:
            if self.openai_client:
                response = await asyncio.wait_for(
                    self.openai_client.chat.completions.create(
                        model=settings.LLM_MODEL_NAME,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=settings.LLM_TEMPERATURE,
                        max_tokens=settings.HYDE_MAX_TOKENS,
                    ),
                    timeout=30.0,
                )
                expanded_text = response.choices[0].message.content

            elif self.hf_client:
                response = await asyncio.wait_for(
                    self.hf_client.chat_completion(
                        model=settings.LLM_MODEL_NAME,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=settings.LLM_TEMPERATURE,
                        max_tokens=settings.HYDE_MAX_TOKENS,
                    ),
                    timeout=30.0,
                )
                expanded_text = response.choices[0].message.content

            else:
                return query

            logger.info("HyDE expansion succeeded (%d chars → %d chars)", len(query), len(expanded_text))
            # Combine the original query with the hypothetical document for maximum recall
            return f"{query}\n\n{expanded_text}"

        except asyncio.TimeoutError:
            logger.warning("HyDE expansion timed out after 30s; using raw query")
            return query
        except Exception as e:
            logger.warning("HyDE expansion failed (%s); using raw query", e)
            return query
