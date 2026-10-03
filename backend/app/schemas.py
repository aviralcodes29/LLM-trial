from typing import List, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Schema for service health check response."""
    status: str = Field(..., example="ok")


# ---------------------------------------------------------------------------
# Chat schemas
# ---------------------------------------------------------------------------

class SourceCitation(BaseModel):
    """A retrieved context chunk cited in the response.

    Field names match the Phase 3 contract: filename, page, snippet, score.
    Legacy aliases (document_name, text_snippet, etc.) are also kept as properties
    so existing frontend code continues to work during the migration.
    """
    filename: str
    page: Optional[int] = None
    snippet: str
    score: float = Field(..., description="Cosine similarity score [0, 1]")
    chunk_id: Optional[str] = None

    # Back-compat properties for the existing MessageBubble component
    @property
    def document_name(self) -> str:
        return self.filename

    @property
    def text_snippet(self) -> str:
        return self.snippet

    @property
    def page_number(self) -> Optional[int]:
        return self.page


class ChatMessage(BaseModel):
    """Individual message in a conversation history."""
    role: str = Field(..., description="Role of the sender: 'user' or 'assistant'")
    content: str = Field(..., description="Message text")


class ChatRequest(BaseModel):
    """Incoming user chat question — Phase 3 contract."""
    question: Optional[str] = Field(None, description="User question (Phase 3)")
    query: Optional[str] = Field(None, description="Alias for question (legacy)")
    doc_ids: Optional[List[str]] = Field(None, description="Restrict search to these doc IDs")
    chat_history: Optional[List[ChatMessage]] = Field(default_factory=list, description="Previous messages")

    def get_question(self) -> str:
        """Return the question, preferring 'question' over the legacy 'query' field."""
        return (self.question or self.query or "").strip()


class ChatResponse(BaseModel):
    """RAG assistant answer with source citations — Phase 3 contract."""
    answer: str = Field(..., description="Generated answer grounded in documents")
    sources: List[SourceCitation] = Field(
        default_factory=list,
        description="Cited document excerpts [{filename, page, snippet, score}]",
    )


# ---------------------------------------------------------------------------
# Document management schemas
# ---------------------------------------------------------------------------

class DocumentInfo(BaseModel):
    """An uploaded document item in the library."""
    doc_id: str
    filename: str
    chunks_count: int
    upload_time: Optional[str] = None
    file_type: Optional[str] = None


class DocumentUploadResponse(BaseModel):
    """Response for document upload and ingestion."""
    doc_id: str
    filename: str
    chunks_count: int
    number_of_chunks: Optional[int] = None
    message: str = "Document successfully ingested."


class DocumentListResponse(BaseModel):
    """Response for listing all ingested documents."""
    documents: List[DocumentInfo]
    total_documents: int


class DeleteDocumentResponse(BaseModel):
    """Response for deleting a document."""
    doc_id: str
    message: str
    deleted_chunks_count: int
