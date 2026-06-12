from typing import List, Dict

class MemoryManager:
    def __init__(self, max_tokens: int = 3000):
        # We define a rough max token limit for conversation history
        # so we don't blow up the context window.
        self.max_tokens = max_tokens

    def _estimate_tokens(self, text: str) -> int:
        """Rough estimation: 1 token ~= 4 chars."""
        return len(text) // 4

    def format_history(self, db_history_records) -> List[Dict]:
        """
        Converts SQLAlchemy ConversationHistory models into the list of dicts
        format expected by the LLM API (e.g., [{'role': 'user', 'content': '...'}])
        It employs a sliding window to keep token count under max_tokens.
        """
        if not db_history_records:
            return []

        formatted = []
        total_tokens = 0
        
        # Traverse history in reverse (newest first) to ensure we keep the most recent context
        for record in reversed(db_history_records):
            # Exclude system messages from history as they are injected fresh every time
            if record.role.value == 'system':
                continue
                
            msg = {"role": record.role.value, "content": record.content}
            msg_tokens = self._estimate_tokens(record.content)
            
            if total_tokens + msg_tokens > self.max_tokens:
                break # Sliding window cutoff reached
                
            formatted.append(msg)
            total_tokens += msg_tokens

        # Reverse again to put back in chronological order
        return list(reversed(formatted))
