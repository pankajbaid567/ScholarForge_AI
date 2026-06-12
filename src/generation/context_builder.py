from typing import List, Dict

class ContextBuilder:
    def __init__(self):
        self.system_prompt_template = """You are an expert academic research assistant (ScholarForge_AI).
Your goal is to answer the user's questions truthfully and comprehensively using ONLY the provided academic context.

Rules:
1. If the context does not contain the answer, say "I cannot find the answer to this question in the provided research papers."
2. Do not hallucinate or use outside knowledge.
3. Use citations when referencing specific claims. Since we have document metadata, cite the author/year if available, or just refer to the context.
4. Format your response in clean Markdown.

### Retrieved Context:
{context_string}
"""

    def build_system_prompt(self, chunks: List[Dict]) -> str:
        """
        Formats retrieved chunks into a single context string to be injected into the system prompt.
        """
        if not chunks:
            return self.system_prompt_template.format(context_string="No relevant context found.")

        context_parts = []
        for index, chunk in enumerate(chunks):
            # Extract metadata
            meta = chunk.get('metadata', {})
            author = meta.get('author', 'Unknown Author')
            year = meta.get('year', 'Unknown Year')
            doc_name = meta.get('filename', 'Unknown Document')
            
            # Format chunk
            part = f"--- Document {index + 1} ({doc_name} | {author}, {year}) ---\n"
            part += f"{chunk.get('text', '')}\n"
            context_parts.append(part)

        context_string = "\n".join(context_parts)
        return self.system_prompt_template.format(context_string=context_string)
