"""Document upload and ingestion endpoint.

Full Phase 2/3 pipeline:
  1. Validate file extension and size.
  2. Extract text and pages via DocumentLoader.
  3. Split text into chunks via TextChunker.
  4. Compute embeddings via GeminiEmbedder.
  5. Save chunks and embeddings into ChromaVectorStore.
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import uuid
import logging

from fastapi import APIRouter, UploadFile, File, HTTPException, status

from app.schemas import DocumentUploadResponse, DocumentListResponse, DocumentInfo, DeleteDocumentResponse
from app.services.loader import DocumentLoader
from app.services.chunker import TextChunker
from app.services.embedder import GeminiEmbedder
from app.services.vectorstore import ChromaVectorStore
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Document Ingestion"])

# ---------------------------------------------------------------------------
# Shared service singletons (created once at module load time)
# ---------------------------------------------------------------------------
_loader = DocumentLoader()
_chunker = TextChunker(chunk_size=800, chunk_overlap=150)
_embedder = GeminiEmbedder(api_key=settings.GEMINI_API_KEY)
_vectorstore = ChromaVectorStore(persist_directory=settings.CHROMA_PATH)

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


# ---------------------------------------------------------------------------
# Ingestion Endpoints (POST /upload and /api/upload)
# ---------------------------------------------------------------------------
@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_200_OK)
@router.post("/api/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_200_OK)
async def upload_document(file: UploadFile = File(...)):
    """Upload, parse, chunk, embed, and index a document for the RAG pipeline.

    Validates:
      - Supported file format (.pdf, .txt, .md)
      - Maximum file size (10 MB)
      - Non-empty content with extractable text

    Returns:
      doc_id, filename, chunks_count, number_of_chunks, and a success message.
    """
    filename = file.filename or "unknown"

    # ── 1. Validate file extension ─────────────────────────────────────────
    if not DocumentLoader.is_supported(filename):
        suffix = Path(filename).suffix.lower()
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{suffix}'. Allowed formats: PDF (.pdf), Text (.txt, .md).",
        )

    # ── 2. Read and validate file size ─────────────────────────────────────
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

    # ── 3. Generate a unique document ID ───────────────────────────────────
    doc_id = str(uuid.uuid4())

    # ── 4. Extract text pages with page numbers ────────────────────────────
    try:
        pages = _loader.load_bytes(file_bytes, filename)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    logger.info(f"[upload] '{filename}' → {len(pages)} pages extracted.")

    # ── 5. Chunk text with metadata preservation ───────────────────────────
    chunks = _chunker.split_pages(pages, doc_id=doc_id)
    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No text chunks could be extracted from '{filename}'.",
        )

    logger.info(f"[upload] '{filename}' → {len(chunks)} chunks produced (size=800, overlap=150).")

    # ── 6. Generate embeddings ─────────────────────────────────────────────
    texts = [c["text"] for c in chunks]
    try:
        embeddings = _embedder.embed_documents(texts)
    except Exception as e:
        logger.error(f"[upload] Embedding failed for '{filename}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Embedding generation failed: {str(e)}",
        )

    # ── 7. Persist to persistent ChromaDB collection ───────────────────────
    try:
        _vectorstore.add_chunks(chunks=chunks, embeddings=embeddings)
    except Exception as e:
        logger.error(f"[upload] ChromaDB insert failed for '{filename}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vector store insertion failed: {str(e)}",
        )

    logger.info(f"[upload] '{filename}' (doc_id={doc_id}) successfully indexed with {len(chunks)} chunks.")

    return DocumentUploadResponse(
        doc_id=doc_id,
        filename=filename,
        chunks_count=len(chunks),
        number_of_chunks=len(chunks),
        message=f"'{filename}' successfully ingested — {len(chunks)} chunks indexed.",
    )


# ---------------------------------------------------------------------------
# Document Listing Endpoints (GET /documents, /api/documents, /api/upload/documents)
# ---------------------------------------------------------------------------
@router.get("/documents", response_model=List[DocumentInfo], tags=["Documents"])
@router.get("/api/documents", response_model=List[DocumentInfo], tags=["Documents"])
async def list_documents():
    """List all indexed documents in the persistent vector store."""
    try:
        docs = _vectorstore.list_documents()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

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
async def list_documents_wrapped():
    """List all indexed documents wrapped in a DocumentListResponse object."""
    try:
        docs = _vectorstore.list_documents()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    doc_infos = [
        DocumentInfo(
            doc_id=d["doc_id"],
            filename=d["filename"],
            chunks_count=d["chunks_count"],
            file_type=d.get("file_type"),
        )
        for d in docs
    ]
    return DocumentListResponse(documents=doc_infos, total_documents=len(doc_infos))


# ---------------------------------------------------------------------------
# Document Inspection Endpoint (GET /documents/{doc_id}/chunks)
# ---------------------------------------------------------------------------
@router.get("/documents/{doc_id}/chunks", tags=["Documents"])
@router.get("/api/documents/{doc_id}/chunks", tags=["Documents"])
async def get_document_chunks(doc_id: str):
    """Retrieve stored chunks and metadata for a given document from ChromaDB."""
    chunks = _vectorstore.get_document_chunks(doc_id)
    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No chunks found for document '{doc_id}'.",
        )
    return {
        "doc_id": doc_id,
        "total_chunks": len(chunks),
        "chunks": chunks,
    }


# ---------------------------------------------------------------------------
# Document Deletion Endpoints (DELETE /documents/{doc_id}, /api/documents/{doc_id})
# ---------------------------------------------------------------------------
@router.delete("/documents/{doc_id}", response_model=DeleteDocumentResponse, tags=["Documents"])
@router.delete("/api/documents/{doc_id}", response_model=DeleteDocumentResponse, tags=["Documents"])
@router.delete("/api/upload/documents/{doc_id}", response_model=DeleteDocumentResponse, tags=["Documents"])
async def delete_document(doc_id: str):
    """Delete all chunks for a given document from the persistent vector store."""
    try:
        deleted = _vectorstore.delete_document(doc_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    if deleted == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No document found with doc_id='{doc_id}'.",
        )

    return DeleteDocumentResponse(
        doc_id=doc_id,
        message=f"Deleted {deleted} chunks for document '{doc_id}'.",
        deleted_chunks_count=deleted,
    )
