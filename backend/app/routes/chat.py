"""Chat query endpoint — Phase 6: Hardened Multi-tenant RAG + Rate Limiting + Usage Tracking.

Features:
  1. Rate limiting (slowapi): 20 chat requests/minute per user.
  2. Multi-tenant isolation: isolated vectorstore & isolated conversation sessions per user.
  3. Token usage and cost tracking in Supabase (raw psycopg2 SQL).
  4. Server-Sent Events (SSE) streaming (/chat and /api/chat with stream=True).
  5. Non-streaming fallback preserved.
  6. Multi-turn memory & follow-up query rewriting.
  7. Strict input validation and global error resilience.
"""

import json
import uuid
import logging
from typing import Optional, Union

from fastapi import APIRouter, HTTPException, Request, Response, Depends, status
from fastapi.responses import StreamingResponse
from psycopg2.extensions import connection as PgConn

from app.schemas import (
    ChatRequest,
    ChatResponse,
    SourceCitation,
    ClearChatRequest,
    ClearChatResponse,
)
from app.services.embedder import GeminiEmbedder
from app.services.vectorstore import ChromaVectorStore, get_vectorstore_for_user
from app.services.llm import GeminiLLM, FALLBACK_MESSAGE
from app.services.memory import session_memory
from app.services.auth import get_current_user
from app.services.rate_limiter import limiter
from app.services.usage import record_usage, estimate_token_count
from app.db.database import get_conn
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat"])

# ---------------------------------------------------------------------------
# Shared service singletons
# ---------------------------------------------------------------------------
_embedder = GeminiEmbedder(api_key=settings.GEMINI_API_KEY)
_llm = GeminiLLM(
    api_key=settings.GEMINI_API_KEY,
    model_name=settings.GEMINI_MODEL,
    relevance_threshold=settings.RELEVANCE_THRESHOLD,
)


def _get_user_session_key(current_user: dict, raw_session_id: str) -> str:
    """Namespace session memory by user ID for multi-tenant isolation."""
    if current_user["username"] == "guest":
        return raw_session_id
    return f"u{current_user['id']}:{raw_session_id}"


@router.post("/chat/clear", response_model=ClearChatResponse, status_code=status.HTTP_200_OK)
@router.post("/api/chat/clear", response_model=ClearChatResponse, status_code=status.HTTP_200_OK)
async def clear_chat_session(
    payload: Optional[ClearChatRequest] = None,
    current_user: dict = Depends(get_current_user),
):
    """Reset conversation memory for a session (or all user sessions if not specified)."""
    target_session = payload.session_id if payload else None

    if target_session:
        session_key = _get_user_session_key(current_user, target_session)
        session_memory.clear_session(session_key)
        msg = f"Conversation history for session '{target_session}' cleared."
    else:
        if current_user["username"] == "guest":
            session_memory.clear_session(None)
        else:
            session_memory.clear_user_sessions(f"u{current_user['id']}:")
        msg = "All conversation sessions for your account have been cleared."

    logger.info(f"[chat/clear] User '{current_user['username']}': {msg}")
    return ClearChatResponse(
        status="ok",
        message=msg,
        session_id=target_session,
    )


@router.get("/api/chat/history/{session_id}", tags=["Chat"])
async def get_chat_history(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Inspect stored conversation memory turns for a given session."""
    session_key = _get_user_session_key(current_user, session_id)
    history = session_memory.get_history(session_key)
    # Also fallback to raw session_id for tests
    if not history and current_user["username"] == "guest":
        history = session_memory.get_history(session_id)

    return {"session_id": session_id, "messages": history, "count": len(history)}


@router.post(
    "/chat",
    response_model=Optional[ChatResponse],
    status_code=status.HTTP_200_OK,
)
@router.post(
    "/api/chat",
    response_model=Optional[ChatResponse],
    status_code=status.HTTP_200_OK,
)
@limiter.limit(settings.RATE_LIMIT_CHAT)
async def chat_with_docs(
    request: Request,
    body: ChatRequest,
    current_user: dict = Depends(get_current_user),
    conn: PgConn = Depends(get_conn),
) -> Union[ChatResponse, StreamingResponse]:
    """Answer a user question strictly using retrieved document context.

    Enforces:
      - Rate limit: 20 chat requests/minute per user
      - Multi-tenant vector store & conversation memory isolation
      - Token usage and cost logging in Supabase
    """
    question = body.get_question()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request must include a non-empty 'question' field.",
        )

    # Validate maximum question length
    if len(question) > 4000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question is too long (maximum 4000 characters).",
        )

    # ── 1. Resolve Session ID and User Key ────────────────────────────────
    session_id = body.session_id or f"session_{uuid.uuid4().hex[:8]}"
    session_key = _get_user_session_key(current_user, session_id)

    # ── 2. Query Rewriting using Conversation Memory ──────────────────────
    rewritten_query = session_memory.rewrite_query(
        session_id=session_key,
        question=question,
        llm=_llm,
    )

    is_rewritten = (rewritten_query != question)
    if is_rewritten:
        logger.info(
            f"[chat] User '{current_user['username']}' session '{session_id}': Rewritten query: "
            f"'{question}' -> '{rewritten_query}'"
        )
    else:
        logger.info(f"[chat] User '{current_user['username']}' session '{session_id}' query: '{question}'")

    # ── 3. Embed Query (using rewritten query) ────────────────────────────
    try:
        query_embedding = _embedder.embed_query(rewritten_query)
    except Exception as e:
        logger.error(f"[chat] Query embedding failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query embedding failed: {str(e)}",
        )

    # ── 4. Retrieve Nearest Chunks from User's Isolated ChromaDB ──────────
    vectorstore = get_vectorstore_for_user(current_user, persist_directory=settings.CHROMA_PATH)
    try:
        raw_chunks = vectorstore.search(
            query_embedding=query_embedding,
            top_k=settings.RETRIEVAL_TOP_K,
            doc_ids=body.doc_ids if body.doc_ids else None,
        )
        # If guest and empty, fallback to default collection
        if not raw_chunks and current_user["username"] == "guest":
            default_vs = ChromaVectorStore(persist_directory=settings.CHROMA_PATH)
            raw_chunks = default_vs.search(
                query_embedding=query_embedding,
                top_k=settings.RETRIEVAL_TOP_K,
                doc_ids=body.doc_ids if body.doc_ids else None,
            )
    except Exception as e:
        logger.error(f"[chat] Vector store search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vector store search failed: {str(e)}",
        )

    # Filter chunks against relevance threshold
    filtered_chunks = _llm.filter_chunks(raw_chunks)

    if settings.DEBUG_MODE:
        logger.debug(
            f"[DEBUG] User {current_user['username']}: Retrieved {len(raw_chunks)} raw chunks, {len(filtered_chunks)} passed threshold."
        )

    # Determine streaming mode
    accept_header = request.headers.get("accept", "")
    wants_stream = bool(body.stream or "text/event-stream" in accept_header)

    # ── 5. Branch A: SSE Streaming Response ───────────────────────────────
    if wants_stream:
        async def event_generator():
            accumulated_tokens = []

            # 1. Emit rewritten query metadata if contextualized
            if is_rewritten:
                yield (
                    f"data: {json.dumps({'type': 'rewritten_query', 'query': rewritten_query})}\n\n"
                )

            # 2. Stream answer tokens
            if not filtered_chunks:
                accumulated_tokens.append(FALLBACK_MESSAGE)
                yield f"data: {json.dumps({'type': 'token', 'content': FALLBACK_MESSAGE})}\n\n"
                yield f"data: {json.dumps({'type': 'sources', 'sources': []})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"
            else:
                try:
                    async for token in _llm.generate_grounded_answer_stream(
                        query=rewritten_query,
                        filtered_chunks=filtered_chunks,
                    ):
                        accumulated_tokens.append(token)
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                except Exception as stream_err:
                    logger.error(f"[chat] Stream generation failed: {stream_err}")
                    err_payload = {"type": "error", "message": str(stream_err)}
                    yield f"data: {json.dumps(err_payload)}\n\n"
                    return

                # 3. Emit final sources event
                sources_payload = [
                    {
                        "filename": c.get("filename", "unknown"),
                        "page": c.get("page"),
                        "snippet": c.get("text", "")[:300].strip(),
                        "score": round(c.get("score", 0.0), 4),
                        "chunk_id": c.get("chunk_id"),
                    }
                    for c in filtered_chunks
                ]
                yield f"data: {json.dumps({'type': 'sources', 'sources': sources_payload})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"

            # 4. Save completed exchange into session conversation memory
            final_answer = "".join(accumulated_tokens)
            session_memory.add_message(session_key, "user", question)
            session_memory.add_message(session_key, "assistant", final_answer)

            # 5. Track Token Usage & Estimated Cost in Supabase
            context_text = " ".join(c.get("text", "") for c in filtered_chunks)
            prompt_tokens = estimate_token_count(question + " " + context_text)
            completion_tokens = estimate_token_count(final_answer)
            try:
                record_usage(
                    conn=conn,
                    user_id=current_user["id"],
                    endpoint="/chat",
                    model=settings.GEMINI_MODEL,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )
            except Exception as usage_err:
                logger.error(f"Failed to record usage: {usage_err}")

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ── 5. Branch B: Non-Streaming Fallback ────────────────────────────────
    try:
        llm_result = _llm.generate_grounded_answer(
            query=rewritten_query,
            context_chunks=raw_chunks,
        )
    except Exception as e:
        logger.error(f"[chat] LLM generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Answer generation failed: {str(e)}",
        )

    answer: str = llm_result["answer"]
    passed_chunks: list = llm_result.get("filtered_chunks", [])

    sources: list[SourceCitation] = []
    if FALLBACK_MESSAGE.lower() not in answer.lower():
        for chunk in passed_chunks:
            sources.append(
                SourceCitation(
                    filename=chunk.get("filename", "unknown"),
                    page=chunk.get("page"),
                    snippet=chunk.get("text", "")[:300].strip(),
                    score=round(chunk.get("score", 0.0), 4),
                    chunk_id=chunk.get("chunk_id"),
                )
            )

    # Save to conversation memory
    session_memory.add_message(session_key, "user", question)
    session_memory.add_message(session_key, "assistant", answer)

    # Record Token Usage & Cost in Supabase
    context_text = " ".join(c.get("text", "") for c in passed_chunks)
    prompt_tokens = estimate_token_count(question + " " + context_text)
    completion_tokens = estimate_token_count(answer)
    try:
        record_usage(
            conn=conn,
            user_id=current_user["id"],
            endpoint="/chat",
            model=settings.GEMINI_MODEL,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
    except Exception as usage_err:
        logger.error(f"Failed to record usage: {usage_err}")

    return ChatResponse(
        answer=answer,
        sources=sources,
        session_id=session_id,
        rewritten_query=rewritten_query if is_rewritten else None,
    )
