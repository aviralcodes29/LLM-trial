"""Document upload and ingestion endpoint — Phase 6: Multi-tenant Isolation + Rate Limiting.

All database access uses raw psycopg2 SQL queries (no ORM).
"""

from typing import List
from pathlib import Path
import uuid
import logging

from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Depends, status
from psycopg2.extensions import connection as PgConn

from app.schemas import (
    DocumentUploadResponse,
    DocumentListResponse,
    DocumentInfo,
    DeleteDocumentResponse,
)
from app.services.loader import DocumentLoader
from app.services.chunker import TextChunker
from app.services.embedder import GeminiEmbedder
from app.services.vectorstore import ChromaVectorStore, get_vectorstore_for_user
from app.services.auth import get_current_user
from app.services.rate_limiter import limiter
from app.services.usage import record_usage, estimate_token_count
from app.db.database import get_conn
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Document Ingestion"])

# ---------------------------------------------------------------------------
# Shared service singletons
# ---------------------------------------------------------------------------
_loader = DocumentLoader()
_chunker = TextChunker(
    chunk_size=getattr(settings, "CHUNK_SIZE", 800),
    chunk_overlap=getattr(settings, "CHUNK_OVERLAP", 150),
)
_embedder = GeminiEmbedder(api_key=settings.GEMINI_API_KEY)

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


# ---------------------------------------------------------------------------
# POST /upload — ingest document
# ---------------------------------------------------------------------------
@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_200_OK)
@router.post("/api/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_200_OK)
@limiter.limit(settings.RATE_LIMIT_UPLOAD)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    conn: PgConn = Depends(get_conn),
):
    """Upload, parse, chunk, embed, and index a document for the RAG pipeline."""
    filename = file.filename or "unknown"

    # 1. Validate file extension
    if not DocumentLoader.is_supported(filename):
        suffix = Path(filename).suffix.lower()
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{suffix}'. Allowed formats: PDF (.pdf), Text (.txt, .md).",
        )

    # 2. Read and validate file size
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {str(e)}",
        )

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        size_mb = len(file_bytes) / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of 10 MB (received {size_mb:.2f} MB).",
        )

    if not file_bytes or len(file_bytes.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Uploaded file '{filename}' is empty (0 bytes).",
        )

    # 3. Generate unique document ID
    doc_id = str(uuid.uuid4())

    # 4. Extract text pages
    try:
        pages = _loader.load_bytes(file_bytes, filename)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    logger.info(
        f"[upload] User '{current_user['username']}' uploading '{filename}' → {len(pages)} pages extracted."
    )

    # 5. Chunk text
    chunks = _chunker.split_pages(pages, doc_id=doc_id)
    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No text chunks could be extracted from '{filename}'.",
        )

    # 6. Generate embeddings
    texts = [c["text"] for c in chunks]
    try:
        embeddings = _embedder.embed_documents(texts)
    except Exception as e:
        logger.error(f"[upload] Embedding failed for '{filename}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Embedding generation failed: {str(e)}",
        )

    # 7. Persist to user-isolated ChromaDB collection
    vectorstore = get_vectorstore_for_user(current_user, persist_directory=settings.CHROMA_PATH)
    try:
        vectorstore.add_chunks(chunks=chunks, embeddings=embeddings)
    except Exception as e:
        logger.error(f"[upload] ChromaDB insert failed for '{filename}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vector store insertion failed: {str(e)}",
        )

    # 8. Track document ownership in Supabase
    file_type = Path(filename).suffix.lower().lstrip(".")
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_documents (doc_id, user_id, filename, chunks_count, file_type)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (doc_id, current_user["id"], filename, len(chunks), file_type),
        )
    conn.commit()

    # 9. Record embedding token consumption
    total_embedded_text = "".join(texts)
    embedding_tokens = estimate_token_count(total_embedded_text)
    record_usage(
        conn=conn,
        user_id=current_user["id"],
        endpoint="/upload",
        model="text-embedding-004",
        prompt_tokens=embedding_tokens,
        completion_tokens=0,
    )

    logger.info(
        f"[upload] '{filename}' (doc_id={doc_id}) indexed for user '{current_user['username']}' "
        f"with {len(chunks)} chunks."
    )

    return DocumentUploadResponse(
        doc_id=doc_id,
        filename=filename,
        chunks_count=len(chunks),
        number_of_chunks=len(chunks),
        message=f"'{filename}' successfully ingested — {len(chunks)} chunks indexed.",
    )


# ---------------------------------------------------------------------------
# GET /documents — list user's documents
# ---------------------------------------------------------------------------
@router.get("/documents", response_model=List[DocumentInfo], tags=["Documents"])
@router.get("/api/documents", response_model=List[DocumentInfo], tags=["Documents"])
async def list_documents(
    current_user: dict = Depends(get_current_user),
    conn: PgConn = Depends(get_conn),
):
    """List all indexed documents belonging to the authenticated user."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT doc_id, filename, chunks_count, file_type, upload_time
            FROM user_documents
            WHERE user_id = %s
            ORDER BY upload_time DESC
            """,
            (current_user["id"],),
        )
        rows = cur.fetchall()

    if rows:
        return [
            DocumentInfo(
                doc_id=r["doc_id"],
                filename=r["filename"],
                chunks_count=r["chunks_count"],
                file_type=r["file_type"],
                upload_time=r["upload_time"].isoformat() if r["upload_time"] else None,
            )
            for r in rows
        ]

    # Fallback: query ChromaDB directly (guest user / pre-migration docs)
    vectorstore = get_vectorstore_for_user(current_user, persist_directory=settings.CHROMA_PATH)
    try:
        docs = vectorstore.list_documents()
    except Exception as e:
        logger.error(f"Failed to list documents from ChromaDB: {e}")
        return []

    return [
        DocumentInfo(
            doc_id=d["doc_id"],
            filename=d["filename"],
            chunks_count=d["chunks_count"],
            file_type=d.get("file_type"),
        )
        for d in docs
    ]


@router.get("/api/upload/documents", response_model=DocumentListResponse, tags=["Documents"])
async def list_documents_wrapped(
    current_user: dict = Depends(get_current_user),
    conn: PgConn = Depends(get_conn),
):
    """List documents wrapped in DocumentListResponse."""
    doc_infos = await list_documents(current_user=current_user, conn=conn)
    return DocumentListResponse(documents=doc_infos, total_documents=len(doc_infos))


# ---------------------------------------------------------------------------
# GET /documents/{doc_id}/chunks — inspect a document's chunks
# ---------------------------------------------------------------------------
@router.get("/documents/{doc_id}/chunks", tags=["Documents"])
@router.get("/api/documents/{doc_id}/chunks", tags=["Documents"])
async def get_document_chunks(
    doc_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Retrieve stored chunks and metadata for a document owned by the user."""
    vectorstore = get_vectorstore_for_user(current_user, persist_directory=settings.CHROMA_PATH)
    chunks = vectorstore.get_document_chunks(doc_id)
    if not chunks and current_user["username"] == "guest":
        default_vs = ChromaVectorStore(persist_directory=settings.CHROMA_PATH)
        chunks = default_vs.get_document_chunks(doc_id)

    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No chunks found for document '{doc_id}'.",
        )

    return {"doc_id": doc_id, "total_chunks": len(chunks), "chunks": chunks}


# ---------------------------------------------------------------------------
# DELETE /documents/{doc_id} — remove document
# ---------------------------------------------------------------------------
@router.delete("/documents/{doc_id}", response_model=DeleteDocumentResponse, tags=["Documents"])
@router.delete("/api/documents/{doc_id}", response_model=DeleteDocumentResponse, tags=["Documents"])
@router.delete("/api/upload/documents/{doc_id}", response_model=DeleteDocumentResponse, tags=["Documents"])
async def delete_document(
    doc_id: str,
    current_user: dict = Depends(get_current_user),
    conn: PgConn = Depends(get_conn),
):
    """Delete all chunks for a document owned by the user from vector store and database."""
    vectorstore = get_vectorstore_for_user(current_user, persist_directory=settings.CHROMA_PATH)
    try:
        deleted = vectorstore.delete_document(doc_id)
    except Exception as e:
        logger.error(f"Chroma delete failed: {e}")
        deleted = 0

    # Remove from Supabase
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM user_documents WHERE doc_id = %s AND user_id = %s RETURNING id",
            (doc_id, current_user["id"]),
        )
        removed_row = cur.fetchone()
    conn.commit()

    if not removed_row and deleted == 0 and current_user["username"] != "guest":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No document found with doc_id='{doc_id}' for this user.",
        )

    return DeleteDocumentResponse(
        doc_id=doc_id,
        message=f"Deleted document '{doc_id}' successfully.",
        deleted_chunks_count=deleted,
    )
