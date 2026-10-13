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
    """Incoming user chat question — Phase 3 & 4 contract."""
    question: Optional[str] = Field(None, description="User question")
    query: Optional[str] = Field(None, description="Alias for question (legacy)")
    doc_ids: Optional[List[str]] = Field(None, description="Restrict search to these doc IDs")
    chat_history: Optional[List[ChatMessage]] = Field(default_factory=list, description="Previous messages")
    session_id: Optional[str] = Field(None, description="Conversation session ID for multi-turn memory")
    stream: Optional[bool] = Field(False, description="Whether to stream tokens via Server-Sent Events (SSE)")

    def get_question(self) -> str:
        """Return the question, preferring 'question' over the legacy 'query' field."""
        return (self.question or self.query or "").strip()


class ChatResponse(BaseModel):
    """RAG assistant answer with source citations — Phase 3 & 4 contract."""
    answer: str = Field(..., description="Generated answer grounded in documents")
    sources: List[SourceCitation] = Field(
        default_factory=list,
        description="Cited document excerpts [{filename, page, snippet, score}]",
    )
    session_id: Optional[str] = Field(None, description="Active session ID for the conversation")
    rewritten_query: Optional[str] = Field(None, description="Standalone rewritten query used for retrieval")


class ClearChatRequest(BaseModel):
    """Request schema for resetting conversation session memory."""
    session_id: Optional[str] = Field(None, description="Session ID to clear. If None, clears default session.")


class ClearChatResponse(BaseModel):
    """Response schema for resetting conversation session memory."""
    status: str = "ok"
    message: str = "Conversation session cleared successfully."
    session_id: Optional[str] = None


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


# ---------------------------------------------------------------------------
# Authentication & Usage schemas (Phase 6)
# ---------------------------------------------------------------------------

class UserRegisterRequest(BaseModel):
    """Schema for registering a new user."""
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    password: str = Field(..., min_length=6, max_length=128, description="Plaintext password")
    email: Optional[str] = Field(None, max_length=100, description="Optional email address")


class UserLoginRequest(BaseModel):
    """Schema for user login credentials."""
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Plaintext password")


class UserInfo(BaseModel):
    """Public user profile information."""
    id: int
    username: str
    email: Optional[str] = None
    is_active: bool = True


class TokenResponse(BaseModel):
    """JWT bearer token response upon successful registration or login."""
    access_token: str
    token_type: str = "bearer"
    user: UserInfo


class UsageRecordItem(BaseModel):
    """An individual recorded API consumption event."""
    id: int
    endpoint: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float
    timestamp: Optional[str] = None


class UsageSummaryResponse(BaseModel):
    """Aggregated usage and cost summary for a user."""
    user_id: Optional[int] = None
    total_requests: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    recent_records: List[UsageRecordItem] = Field(default_factory=list)
