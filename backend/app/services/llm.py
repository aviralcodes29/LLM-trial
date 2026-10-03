"""LLM service interface and implementations.

Abstracts the generation logic and strict prompt grounding,
allowing easy swapping between Google Gemini, Anthropic Claude, OpenAI, or local Ollama.
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

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
        """Generate an answer strictly grounded in the retrieved document context.

        Args:
            query: User's question.
            context_chunks: Retrieved document passages with citations.
            chat_history: Optional preceding conversational turns.

        Returns:
            Dictionary containing 'answer' (str) and 'prompt' (str, for debug).
        """
        pass


# ---------------------------------------------------------------------------
# Gemini implementation
# ---------------------------------------------------------------------------
class GeminiLLM(BaseLLM):
    """Google Gemini LLM implementation using google-generativeai SDK."""

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
                                 Chunks below this are discarded before calling the LLM.
        """
        self.model_name = model_name
        self.relevance_threshold = relevance_threshold
        self._is_configured = False

        if api_key and not api_key.startswith("dummy"):
            try:
                genai.configure(api_key=api_key)
                self._is_configured = True
                logger.info(f"GeminiLLM initialized with model '{model_name}'.")
            except Exception as e:
                logger.warning(f"Failed to configure Gemini SDK for LLM: {e}")

    def generate_grounded_answer(
        self,
        query: str,
        context_chunks: List[Dict[str, Any]],
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Generate answer strictly grounded in context chunks.

        Applies relevance threshold before calling the model. If no chunk passes
        the threshold the fallback message is returned without an LLM call.

        Returns:
            {
                "answer": str,
                "prompt": str,           # full prompt (for debug logging)
                "filtered_chunks": list, # chunks that passed the threshold
            }
        """
        # ── 1. Apply relevance threshold ──────────────────────────────────
        filtered_chunks = [
            c for c in context_chunks
            if c.get("score", 0) >= self.relevance_threshold
        ]

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

        # ── 2. Build grounded prompt ──────────────────────────────────────
        prompt = _build_prompt(query, filtered_chunks)

        # ── 3. Call Gemini (or stub if not configured) ────────────────────
        if not self._is_configured:
            logger.warning("GeminiLLM not configured (no valid API key). Returning stub answer.")
            answer = (
                "[Gemini API key not configured] Relevant context found in:\n"
                + "\n".join(
                    f"  - {c.get('filename')} page {c.get('page')}: \"{c.get('text', '')[:120]}...\""
                    for c in filtered_chunks
                )
            )
            return {"answer": answer, "prompt": prompt, "filtered_chunks": filtered_chunks}

        try:
            model = genai.GenerativeModel(model_name=self.model_name)
            response = model.generate_content(prompt)
            answer = response.text.strip() if response.text else FALLBACK_MESSAGE
        except Exception as e:
            logger.error(f"Gemini generate_content failed: {e}")
            raise RuntimeError(f"LLM generation failed: {e}") from e

        return {"answer": answer, "prompt": prompt, "filtered_chunks": filtered_chunks}
