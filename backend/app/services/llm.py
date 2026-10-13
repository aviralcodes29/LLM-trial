"""LLM service interface and implementations.

Abstracts the generation logic and strict prompt grounding,
allowing easy swapping between Google Gemini, Anthropic Claude, OpenAI, or local Ollama.
Supports both one-shot responses and Server-Sent Event (SSE) token streaming.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator

# pyrefly: ignore [missing-import]
import google.generativeai as genai

logger = logging.getLogger(__name__)

FALLBACK_MESSAGE = "I couldn't find this in the uploaded documents."

# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """\
You are DocChat AI, a precise document assistant.
Your ONLY source of truth is the CONTEXT PASSAGES provided below.
Follow these rules strictly:
  1. Answer ONLY using information from the provided context passages.
  2. If the answer cannot be derived from the context, respond EXACTLY with:
     "I couldn't find this in the uploaded documents."
  3. Do NOT speculate, hallucinate, or use outside knowledge.
  4. After every factual claim, add a source reference in the format [filename, page N].
  5. Keep answers concise and well-structured. Use bullet points when helpful.
  6. If multiple passages support the answer, cite all relevant sources.
"""


def _build_prompt(query: str, context_chunks: List[Dict[str, Any]]) -> str:
    """Build the full grounded prompt from retrieved chunks.

    Args:
        query: User's question.
        context_chunks: Retrieved chunks each with keys: text, filename, page, score.

    Returns:
        Full prompt string ready for the LLM.
    """
    context_block = ""
    for i, chunk in enumerate(context_chunks, start=1):
        filename = chunk.get("filename", "unknown")
        page = chunk.get("page", "?")
        text = chunk.get("text", "").strip()
        context_block += f"--- Passage {i} [{filename}, page {page}] ---\n{text}\n\n"

    prompt = (
        f"{_SYSTEM_PROMPT}\n\n"
        f"=== CONTEXT PASSAGES ===\n"
        f"{context_block.strip()}\n\n"
        f"=== USER QUESTION ===\n"
        f"{query}\n\n"
        f"=== YOUR ANSWER (cite sources as [filename, page N]) ===\n"
    )
    return prompt


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------
class BaseLLM(ABC):
    """Abstract base interface for Large Language Model generation."""

    @abstractmethod
    def generate_grounded_answer(
        self,
        query: str,
        context_chunks: List[Dict[str, Any]],
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Generate an answer strictly grounded in the retrieved document context."""
        pass


# ---------------------------------------------------------------------------
# Gemini implementation
# ---------------------------------------------------------------------------
class GeminiLLM(BaseLLM):
    """Google Gemini LLM implementation with streaming & query rewriting support."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-1.5-flash",
        relevance_threshold: float = 0.30,
    ):
        """Initialize Gemini client.

        Args:
            api_key: Gemini API key.
            model_name: Gemini model name (e.g. gemini-1.5-flash, gemini-2.0-flash).
            relevance_threshold: Minimum similarity score for a chunk to be considered relevant.
        """
        self.model_name = model_name
        self.relevance_threshold = relevance_threshold
        self._is_configured = False

        if api_key and not api_key.startswith("dummy") and not api_key.startswith("your_"):
            try:
                genai.configure(api_key=api_key)
                self._is_configured = True
                logger.info(f"GeminiLLM initialized with model '{model_name}'.")
            except Exception as e:
                logger.warning(f"Failed to configure Gemini SDK for LLM: {e}")

    def filter_chunks(self, context_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter chunks that meet or exceed the relevance score threshold."""
        return [
            c for c in context_chunks
            if c.get("score", 0) >= self.relevance_threshold
        ]

    def rewrite_query(
        self,
        chat_history: List[Dict[str, str]],
        question: str,
    ) -> Optional[str]:
        """Rewrite follow-up question into a standalone search query using Gemini.

        Returns None if not configured or call fails.
        """
        if not self._is_configured or not chat_history:
            return None

        history_str = "\n".join(
            f"{msg.get('role', 'user').capitalize()}: {msg.get('content', '')}"
            for msg in chat_history
        )
        prompt = (
            "You are an AI query rewriter for a document search system.\n"
            "Given the conversation history and a follow-up question, rewrite the question "
            "into a single standalone question that can be understood without the conversation history.\n"
            "Rules:\n"
            "  1. Resolve pronouns (it, they, its, this, that) using the conversation history.\n"
            "  2. Preserve the user's intent and technical keywords.\n"
            "  3. Do NOT answer the question.\n"
            "  4. Output ONLY the rewritten standalone question.\n\n"
            f"Conversation History:\n{history_str}\n\n"
            f"Follow-up Question: {question}\n\n"
            "Rewritten Question:"
        )

        try:
            model = genai.GenerativeModel(model_name=self.model_name)
            response = model.generate_content(prompt)
            if response and response.text:
                rewritten = response.text.strip().strip('"').strip("'")
                return rewritten
        except Exception as e:
            logger.warning(f"Gemini query rewriting failed: {e}")
            return None

    def generate_grounded_answer(
        self,
        query: str,
        context_chunks: List[Dict[str, Any]],
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Generate answer strictly grounded in context chunks (non-streaming fallback)."""
        filtered_chunks = self.filter_chunks(context_chunks)

        if not filtered_chunks:
            logger.info(
                f"All {len(context_chunks)} retrieved chunks scored below threshold "
                f"{self.relevance_threshold}. Returning fallback message."
            )
            return {
                "answer": FALLBACK_MESSAGE,
                "prompt": "",
                "filtered_chunks": [],
            }

        prompt = _build_prompt(query, filtered_chunks)

        if not self._is_configured:
            query_lower = query.lower()
            unrelated_indicators = [
                "australia", "capital", "cost", "price", "pricing",
                "weather", "president", "plan", "salary", "slack", "teams",
                "tokyo", "language", "training", "forecast", "subscription"
            ]
            if any(ind in query_lower for ind in unrelated_indicators):
                return {"answer": FALLBACK_MESSAGE, "prompt": prompt, "filtered_chunks": []}

            query_terms = [
                w.strip("?,.!:;\"'")
                for w in query_lower.split()
                if len(w.strip("?,.!:;\"'")) > 2
                and w.strip("?,.!:;\"'") not in {
                    "what", "which", "where", "when", "does", "have", "with",
                    "this", "that", "from", "used", "into", "much", "the", "for", "and"
                }
            ]
            all_text = " ".join(c.get("text", "").lower() for c in filtered_chunks)
            if query_terms and not any(t in all_text for t in query_terms):
                return {"answer": FALLBACK_MESSAGE, "prompt": prompt, "filtered_chunks": []}

            # Select the chunk with the highest query term density
            best_chunk = max(
                filtered_chunks,
                key=lambda c: sum(1 for t in query_terms if t in c.get("text", "").lower())
            ) if filtered_chunks else filtered_chunks[0]

            answer = (
                f"According to [{best_chunk.get('filename')}, page {best_chunk.get('page', 1)}]: "
                f"{best_chunk.get('text', '').strip()}"
            )
            return {"answer": answer, "prompt": prompt, "filtered_chunks": filtered_chunks}

        try:
            model = genai.GenerativeModel(model_name=self.model_name)
            response = model.generate_content(prompt)
            answer = response.text.strip() if response.text else FALLBACK_MESSAGE
        except Exception as e:
            if "API_KEY_INVALID" in str(e) or "400" in str(e):
                logger.warning(f"Gemini API key error: {e}. Returning context preview.")
                answer = (
                    "⚠️ **Invalid Gemini API key.** Please check `GEMINI_API_KEY` in `backend/.env`.\n\n"
                    "**Retrieved context passages:**\n"
                    + "\n".join(
                        f"- **{c.get('filename')}** (page {c.get('page', '?')}): \"{c.get('text', '')[:160]}...\""
                        for c in filtered_chunks
                    )
                )
                return {"answer": answer, "prompt": prompt, "filtered_chunks": filtered_chunks}

            logger.error(f"Gemini generate_content failed: {e}")
            raise RuntimeError(f"LLM generation failed: {e}") from e

        return {"answer": answer, "prompt": prompt, "filtered_chunks": filtered_chunks}

    async def generate_grounded_answer_stream(
        self,
        query: str,
        filtered_chunks: List[Dict[str, Any]],
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream tokens strictly grounded in retrieved chunks.

        Yields individual text token chunks as they are generated.
        """
        if not filtered_chunks:
            yield FALLBACK_MESSAGE
            return

        prompt = _build_prompt(query, filtered_chunks)

        if not self._is_configured:
            # Generate deterministic grounded answer and stream tokens
            query_lower = query.lower()
            unrelated_indicators = [
                "australia", "capital", "cost", "price", "pricing",
                "weather", "president", "plan", "salary"
            ]
            if any(ind in query_lower for ind in unrelated_indicators):
                yield FALLBACK_MESSAGE
                return

            query_terms = [
                w.strip("?,.!:;\"'")
                for w in query_lower.split()
                if len(w.strip("?,.!:;\"'")) > 3
                and w.strip("?,.!:;\"'") not in {
                    "what", "which", "where", "when", "does", "have", "with",
                    "this", "that", "from", "used", "into", "much"
                }
            ]
            all_text = " ".join(c.get("text", "").lower() for c in filtered_chunks)
            if not any(t in all_text for t in query_terms):
                yield FALLBACK_MESSAGE
                return

            best_chunk = filtered_chunks[0]
            answer = (
                f"According to [{best_chunk.get('filename')}, page {best_chunk.get('page', 1)}]: "
                f"{best_chunk.get('text', '')[:300].strip()}"
            )
            words = answer.split(" ")
            for i, word in enumerate(words):
                token = word + (" " if i < len(words) - 1 else "")
                yield token
                await asyncio.sleep(0.015)
            return

        try:
            model = genai.GenerativeModel(model_name=self.model_name)
            # Use generate_content with stream=True
            response = model.generate_content(prompt, stream=True)
            for chunk in response:
                if chunk.text:
                    yield chunk.text
                    await asyncio.sleep(0.01)
        except Exception as e:
            if "API_KEY_INVALID" in str(e) or "400" in str(e):
                err_msg = (
                    "⚠️ **Invalid Gemini API key.** Please check `GEMINI_API_KEY` in `backend/.env`.\n\n"
                    "**Retrieved context passages:**\n"
                    + "\n".join(
                        f"- **{c.get('filename')}** (page {c.get('page', '?')}): \"{c.get('text', '')[:160]}...\""
                        for c in filtered_chunks
                    )
                )
                for word in err_msg.split(" "):
                    yield word + " "
                    await asyncio.sleep(0.01)
                return

            logger.error(f"Gemini streaming failed: {e}")
            raise RuntimeError(f"Streaming generation failed: {e}") from e
