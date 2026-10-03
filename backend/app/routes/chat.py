"""Chat query endpoint — Phase 3: Retrieval + Answer Generation.

RAG pipeline per request:
  1. Embed user question via GeminiEmbedder.
  2. Search nearest chunks via ChromaVectorStore (with optional doc_id filter).
  3. Apply relevance threshold — skip LLM if no chunk qualifies.
  4. Build grounded prompt and call GeminiLLM.
  5. Return answer + source citations.

Debug mode (DEBUG_MODE=true in .env):
  - Logs each retrieved chunk (chunk_id, score, page, filename, text preview).
  - Logs the full LLM prompt.
"""

import logging

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, HTTPException, status

from app.schemas import ChatRequest, ChatResponse, SourceCitation
from app.services.embedder import GeminiEmbedder
from app.services.vectorstore import ChromaVectorStore
from app.services.llm import GeminiLLM, FALLBACK_MESSAGE
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat"])

# ---------------------------------------------------------------------------
# Shared service singletons
# ---------------------------------------------------------------------------
_embedder = GeminiEmbedder(api_key=settings.GEMINI_API_KEY)
_vectorstore = ChromaVectorStore(persist_directory=settings.CHROMA_PATH)
_llm = GeminiLLM(
    api_key=settings.GEMINI_API_KEY,
    model_name=settings.GEMINI_MODEL,
    relevance_threshold=settings.RELEVANCE_THRESHOLD,
)


@router.post("", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat_with_docs(request: ChatRequest):
    """Answer a user question strictly using retrieved document context.

    Body:
        question (str): The user's question.
        doc_ids (list[str], optional): Restrict retrieval to these document IDs.

    Returns:
        answer (str): Grounded answer (or fallback message if not found).
        sources (list): [{filename, page, snippet, score}] for each cited chunk.
    """
    question = request.get_question()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request must include a non-empty 'question' field.",
        )

    logger.info(f"[chat] Question: '{question[:120]}' | doc_ids filter: {request.doc_ids}")

    # ── 1. Embed query ────────────────────────────────────────────────────
    try:
        query_embedding = _embedder.embed_query(question)
    except Exception as e:
        logger.error(f"[chat] Query embedding failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query embedding failed: {str(e)}",
        )

    # ── 2. Retrieve nearest chunks ────────────────────────────────────────
    try:
        raw_chunks = _vectorstore.search(
            query_embedding=query_embedding,
            top_k=settings.RETRIEVAL_TOP_K,
            doc_ids=request.doc_ids if request.doc_ids else None,
        )
    except Exception as e:
        logger.error(f"[chat] Vector store search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vector store search failed: {str(e)}",
        )

    # ── 3. Debug log: retrieved chunks ────────────────────────────────────
    if settings.DEBUG_MODE:
        logger.debug(f"[DEBUG] Retrieved {len(raw_chunks)} raw chunks:")
        for i, c in enumerate(raw_chunks, 1):
            logger.debug(
                f"  [{i}] chunk_id={c.get('chunk_id')} | score={c.get('score'):.4f} | "
                f"file={c.get('filename')} | page={c.get('page')} | "
                f"text_preview={repr(c.get('text', '')[:120])}"
            )

    # ── 4. Call LLM (threshold applied inside GeminiLLM) ─────────────────
    try:
        llm_result = _llm.generate_grounded_answer(
            query=question,
            context_chunks=raw_chunks,
        )
    except Exception as e:
        logger.error(f"[chat] LLM generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Answer generation failed: {str(e)}",
        )

    answer: str = llm_result["answer"]
    filtered_chunks: list = llm_result.get("filtered_chunks", [])

    # ── 5. Debug log: prompt ──────────────────────────────────────────────
    if settings.DEBUG_MODE and llm_result.get("prompt"):
        logger.debug(f"[DEBUG] Full prompt sent to LLM:\n{llm_result['prompt']}")

    # ── 6. Build source citations from filtered chunks ────────────────────
    sources: list[SourceCitation] = []
    if answer != FALLBACK_MESSAGE:
        for chunk in filtered_chunks:
            sources.append(
                SourceCitation(
                    filename=chunk.get("filename", "unknown"),
                    page=chunk.get("page"),
                    snippet=chunk.get("text", "")[:300].strip(),
                    score=round(chunk.get("score", 0.0), 4),
                    chunk_id=chunk.get("chunk_id"),
                )
            )

    logger.info(
        f"[chat] Answer generated. "
        f"Chunks retrieved: {len(raw_chunks)}, passed threshold: {len(filtered_chunks)}, "
        f"fallback: {answer == FALLBACK_MESSAGE}"
    )

    return ChatResponse(answer=answer, sources=sources)
