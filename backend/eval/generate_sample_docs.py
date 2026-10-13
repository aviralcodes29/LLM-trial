"""Generate sample evaluation documents (PDF and TXT) for DocChat AI Phase 5 evaluation."""

import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

DOC_PAGES = [
    # Page 1
    (
        "DocChat AI Architecture & Document Loader - Page 1\n\n"
        "DocChat AI is an enterprise-grade document intelligence platform powered by Retrieval-Augmented "
        "Generation (RAG). The system establishes a robust Document Ingestion Pipeline designed to parse "
        "diverse document formats, decompose them into semantically cohesive passages, compute high-dimensional "
        "vector representations, and index them into a persistent vector database.\n\n"
        "The DocumentLoader service is responsible for ingesting files from in-memory byte buffers or the local "
        "filesystem. For Portable Document Format (PDF) files, the DocumentLoader uses pypdf to parse the binary "
        "object graph, inspect page dictionaries, and extract clean text streams while meticulously preserving the "
        "source page numbers. This page preservation ensures that subsequent citation modules can provide exact "
        "page-level source references for every assertion made by the language model.\n\n"
        "The system enforces a strict maximum file upload size of 10 MB. Files exceeding 10 MB or featuring unsupported "
        "extensions are immediately rejected with an HTTP 400 Bad Request error to ensure resource integrity."
    ),
    # Page 2
    (
        "DocChat AI Chunking & Embedding Pipeline - Page 2\n\n"
        "Text chunking is executed by the TextChunker service. Rather than arbitrarily slicing strings at rigid byte "
        "boundaries, the chunker employs a sliding-window strategy calibrated to approximately 800 characters per chunk "
        "with an intentional 150-character overlap between adjacent segments.\n\n"
        "This overlap prevents semantic cliff effects where critical context, sentence clauses, or named entities are "
        "split across retrieval boundaries. Furthermore, the chunker inspects natural linguistic delimiters such as "
        "paragraph breaks, sentence periods, question marks, semicolons, and commas to position segment borders naturally.\n\n"
        "Each generated chunk is enriched with essential metadata: doc_id, filename, source page number, global chunk "
        "index, and character count. These chunks are then dispatched to the GeminiEmbedder, which batches requests into "
        "groups of 20 and interfaces with Google Gemini text-embedding-004. Rate-limiting errors such as HTTP 429 and "
        "ResourceExhausted are gracefully mitigated through exponential backoff with jitter."
    ),
    # Page 3
    (
        "DocChat AI Vector Storage & Persistence - Page 3\n\n"
        "Once vector embeddings are generated, chunks and their metadata are committed to a persistent ChromaDB "
        "collection named docchat_docs via ChromaVectorStore. ChromaDB persists vector indexes to the local filesystem "
        "using Hierarchical Navigable Small World (HNSW) graphs configured with cosine similarity distance metrics.\n\n"
        "The ChromaVectorStore exposes three core methods: add_chunks() for upserting vectorized content with metadata, "
        "list_documents() for inventorying indexed documents with aggregated chunk counts, and delete_document(doc_id) "
        "for atomic deletion of all vector chunks associated with an unindexed document.\n\n"
        "This storage architecture guarantees high retrieval accuracy, sub-50ms vector query latencies, and deterministic "
        "isolation between distinct documents."
    ),
    # Page 4
    (
        "DocChat AI Retrieval & Grounded Generation - Page 4\n\n"
        "The GeminiLLM service interfaces with Google Gemini 1.5 Flash to synthesize answers grounded strictly in retrieved "
        "context passages. The prompt instructs the model to answer ONLY from the provided passages and format source "
        "citations as [filename, page N].\n\n"
        "A relevance score threshold of 0.30 is strictly enforced on retrieved chunks. If no retrieved chunk meets or "
        "exceeds this threshold, the pipeline skips the LLM call entirely and immediately returns the fallback message: "
        "\"I couldn't find this in the uploaded documents.\"\n\n"
        "By enforcing strict negative constraints, DocChat AI completely prevents hallucinations and avoids speculative "
        "assertions beyond the source documents."
    ),
    # Page 5
    (
        "DocChat AI Streaming, Memory & UX - Page 5\n\n"
        "In Phase 4, the /chat endpoint streams responses via Server-Sent Events (SSE) with media type text/event-stream. "
        "The server emits progressive token events (data: {\"type\": \"token\", \"content\": \"...\"}), followed by a "
        "sources citation event (data: {\"type\": \"sources\", \"sources\": [...]}), and finishes with a done event.\n\n"
        "Conversation memory maintains a sliding window of the last 6 messages per session_id. Prior to vector retrieval, "
        "follow-up queries containing pronouns or conversational ellipsis are rewritten by the LLM into standalone search "
        "queries to ensure high semantic recall. The POST /chat/clear endpoint resets the conversation memory for any session."
    ),
]


def write_raw_pdf(file_path: Path, pages_text: list):
    """Write valid 5-page PDF with extractable text."""
    objects = []

    def add_obj(content):
        objects.append(content)
        return len(objects)

    # 1: Catalog
    add_obj(b"<< /Type /Catalog /Pages 2 0 R >>")
    # 2: Pages (placeholder)
    pages_obj_idx = 2
    objects.append(b"")

    page_refs = []
    font_obj_idx = add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for text in pages_text:
        clean = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        lines = [line.strip() for line in clean.split("\n") if line.strip()]
        stream_cmds = ["BT", "/F1 11 Tf", "50 750 Td", "14 TL"]
        for l in lines:
            stream_cmds.append(f"({l}) '")
        stream_cmds.append("ET")
        stream_bytes = "\n".join(stream_cmds).encode("latin-1")

        content_obj_idx = add_obj(
            f"<< /Length {len(stream_bytes)} >>\nstream\n".encode("latin-1")
            + stream_bytes
            + b"\nendstream"
        )
        page_obj_idx = add_obj(
            f"<< /Type /Page /Parent {pages_obj_idx} 0 R /MediaBox [0 0 612 792] /Contents {content_obj_idx} 0 R /Resources << /Font << /F1 {font_obj_idx} 0 R >> >> >>".encode(
                "latin-1"
            )
        )
        page_refs.append(f"{page_obj_idx} 0 R")

    kids_str = " ".join(page_refs)
    objects[pages_obj_idx - 1] = f"<< /Type /Pages /Kids [{kids_str}] /Count {len(page_refs)} >>".encode("latin-1")

    out = bytearray(b"%PDF-1.4\n")
    xref = [0]
    for i, obj in enumerate(objects):
        xref.append(len(out))
        out.extend(f"{i + 1} 0 obj\n".encode("latin-1"))
        out.extend(obj)
        out.extend(b"\nendobj\n")

    xref_offset = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("latin-1"))
    for offset in xref[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))

    out.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("latin-1")
    )

    file_path.write_bytes(out)


def generate_docs():
    output_dir = Path(__file__).resolve().parent / "sample_docs"
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_path = output_dir / "sample_document.pdf"
    write_raw_pdf(pdf_path, DOC_PAGES)
    print(f"Generated PDF at: {pdf_path} ({pdf_path.stat().st_size} bytes)")

    txt_path = output_dir / "sample_document.txt"
    full_text = "\n\n--- PAGE BREAK ---\n\n".join(DOC_PAGES)
    txt_path.write_text(full_text, encoding="utf-8")
    print(f"Generated TXT at: {txt_path} ({txt_path.stat().st_size} bytes)")


if __name__ == "__main__":
    generate_docs()
