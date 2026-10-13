"""Conversation memory and query rewriting service for DocChat AI.

Maintains in-memory session history (last 6 messages per session)
and rewrites follow-up questions into standalone queries before retrieval.
"""

import re
import logging
from collections import deque
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class ConversationMemory:
    """Manages short-term conversation history and query contextualization."""

    def __init__(self, max_messages: int = 6):
        """Initialize session storage.

        Args:
            max_messages: Maximum number of recent messages to preserve per session (default 6).
        """
        self.max_messages = max_messages
        # Mapping: session_id -> deque of {"role": str, "content": str}
        self._sessions: Dict[str, deque] = {}

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """Return the conversation history for a given session."""
        if not session_id or session_id not in self._sessions:
            return []
        return list(self._sessions[session_id])

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Append a message to the session's sliding history window."""
        if not session_id:
            return
        if session_id not in self._sessions:
            self._sessions[session_id] = deque(maxlen=self.max_messages)
        self._sessions[session_id].append({"role": role, "content": content.strip()})
        logger.debug(
            f"[Memory] Added '{role}' message to session '{session_id}'. "
            f"Current history length: {len(self._sessions[session_id])}"
        )

    def clear_session(self, session_id: Optional[str] = None) -> bool:
        """Clear conversation history for a session (or all sessions if None)."""
        if session_id is None:
            self._sessions.clear()
            logger.info("[Memory] Cleared all session histories.")
            return True
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"[Memory] Cleared session history for '{session_id}'.")
            return True
        return False

    def clear_user_sessions(self, user_prefix: str) -> int:
        """Clear all sessions matching a user prefix."""
        keys = [k for k in self._sessions if k.startswith(user_prefix)]
        for k in keys:
            del self._sessions[k]
        logger.info(f"[Memory] Cleared {len(keys)} sessions for prefix '{user_prefix}'.")
        return len(keys)

    def rewrite_query(
        self,
        session_id: str,
        question: str,
        llm: Optional[Any] = None,
    ) -> str:
        """Rewrite follow-up question into a standalone query using context.

        If the conversation history is empty or question is already self-contained,
        returns original question. Otherwise, uses LLM if configured or a rule-based
        fallback entity extractor.

        Args:
            session_id: Current session identifier.
            question: User's raw question input.
            llm: Optional LLM instance for generative rewriting.

        Returns:
            Rewritten standalone question string.
        """
        history = self.get_history(session_id)
        cleaned_question = question.strip()

        if not history:
            return cleaned_question

        # Try LLM-based query rewrite if LLM instance is provided and configured
        if llm and hasattr(llm, "rewrite_query"):
            try:
                rewritten = llm.rewrite_query(history, cleaned_question)
                if rewritten and rewritten.strip():
                    logger.info(
                        f"[Memory] LLM rewritten query for '{session_id}': "
                        f"'{cleaned_question}' -> '{rewritten.strip()}'"
                    )
                    return rewritten.strip()
            except Exception as e:
                logger.warning(f"[Memory] LLM query rewriting failed: {e}. Falling back to rule-based.")

        # Fallback rule-based pronoun/reference resolution
        return self._rule_based_rewrite(history, cleaned_question)

    def _rule_based_rewrite(self, history: List[Dict[str, str]], question: str) -> str:
        """Deterministic fallback to rewrite questions containing pronouns or ellipsis."""
        lower_q = question.lower()
        pronouns_regex = r"\b(it|its|they|them|their|this|that|these|those)\b"
        has_pronoun = bool(re.search(pronouns_regex, lower_q))
        starts_with_ellipsis = any(
            lower_q.startswith(prefix)
            for prefix in ["how does it", "what about", "how about", "explain it", "and it", "why does it", "does it", "can it"]
        )

        if not (has_pronoun or starts_with_ellipsis):
            return question

        # Extract dominant subject/entity from the most recent user turn or assistant turn
        subject = self._extract_subject_from_history(history)
        if not subject:
            return question

        # If question starts with "how does it", replace "it" with subject
        if "how does it" in lower_q:
            rewritten = re.sub(r"\bhow does it\b", f"how does {subject}", question, flags=re.IGNORECASE)
            return rewritten

        if "what does it" in lower_q:
            rewritten = re.sub(r"\bwhat does it\b", f"what does {subject}", question, flags=re.IGNORECASE)
            return rewritten

        if "why does it" in lower_q:
            rewritten = re.sub(r"\bwhy does it\b", f"why does {subject}", question, flags=re.IGNORECASE)
            return rewritten

        if "what about" in lower_q:
            rewritten = re.sub(r"\bwhat about\b", f"what about {subject}", question, flags=re.IGNORECASE)
            return rewritten

        # Replace single pronoun "it" or "its"
        rewritten = re.sub(r"\bit\b", subject, question, flags=re.IGNORECASE)
        rewritten = re.sub(r"\bits\b", f"{subject}'s", rewritten, flags=re.IGNORECASE)

        if rewritten != question:
            logger.info(f"[Memory] Rule-based rewritten query: '{question}' -> '{rewritten}'")
            return rewritten

        # If question is short (e.g. "What about overlap?"), prepend subject context
        return f"{subject}: {question}"

    def _extract_subject_from_history(self, history: List[Dict[str, str]]) -> Optional[str]:
        """Extract primary subject entity from preceding conversation turns."""
        # Check user turns first, in reverse order
        for msg in reversed(history):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                # Look for known architecture terms
                known_terms = [
                    "TextChunker", "DocumentLoader", "ChromaVectorStore", "GeminiEmbedder",
                    "GeminiLLM", "ChromaDB", "DocChat AI", "PDF", "chunk size", "overlap"
                ]
                for term in known_terms:
                    if term.lower() in content.lower():
                        return term

                # Fallback: find capitalized words or first significant noun phrase
                words = content.split()
                proper_nouns = [w.strip("?,.!:;\"'") for w in words if w and w[0].isupper() and w.lower() not in {"what", "how", "why", "when", "is", "does", "the", "a", "an", "can"}]
                if proper_nouns:
                    return proper_nouns[0]

        return None


# Global memory manager singleton
session_memory = ConversationMemory(max_messages=6)
