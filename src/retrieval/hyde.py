from openai import AsyncOpenAI
from src.core.config import get_settings

settings = get_settings()

class HyDEExpander:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
        
    async def expand_query(self, query: str) -> str:
        """
        Uses Hypothetical Document Embeddings (HyDE) to expand a short query 
        into a richer academic context paragraph.
        """
        if not self.client:
            return query # Fallback if no API key
            
        prompt = (
            f"Please write a short, precise academic paragraph answering the following question. "
            f"Use formal academic vocabulary and concepts. Do not include introductory filler. \n\n"
            f"Question: {query}"
        )
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=150
            )
            expanded_text = response.choices[0].message.content
            # Combine the original query with the hypothetical document for maximum recall
            return f"{query}\n\n{expanded_text}"
        except Exception:
            # Fallback to the original query if the LLM call fails
            return query
