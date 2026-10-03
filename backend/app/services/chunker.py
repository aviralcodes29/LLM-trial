"""Document chunker service.

Splits extracted document texts into uniform, overlapping chunks suitable
for vector embeddings and retrieval context windows.
"""

from typing import List, Dict, Any


class TextChunker:
    """Service for splitting text into overlapping chunks with metadata preservation."""

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 150):
        """Initialize chunker with configurable size and overlap.

        Args:
            chunk_size: Maximum character count per chunk (default 800).
            chunk_overlap: Overlapping character count between consecutive chunks (default 150).
        """
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be strictly smaller than chunk_size.")
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive.")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_pages(
        self,
        pages: List[Dict[str, Any]],
        doc_id: str,
    ) -> List[Dict[str, Any]]:
        """Split a list of extracted pages into chunks with full metadata.

        Args:
            pages: List of dicts with {"text", "page_number", "filename"}.
            doc_id: Unique identifier for the parent document.

        Returns:
            List of chunk dicts:
            [
                {
                    "chunk_id": "doc123_p1_c0",
                    "text": "...",
                    "metadata": {
                        "doc_id": "doc123",
                        "filename": "sample.pdf",
                        "page_number": 1,
                        "chunk_index": 0,
                        "char_count": 782,
                    }
                }
            ]
        """
        chunks: List[Dict[str, Any]] = []
        global_chunk_idx = 0

        for page in pages:
            page_text = page["text"]
            page_num = page["page_number"]
            filename = page["filename"]

            page_chunks = self._chunk_single_text(page_text)

            for local_idx, chunk_text in enumerate(page_chunks):
                chunk_id = f"{doc_id}_p{page_num}_c{local_idx}"
                chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "text": chunk_text,
                        "metadata": {
                            "doc_id": doc_id,
                            "filename": filename,
                            "page_number": int(page_num),
                            "chunk_index": int(global_chunk_idx),
                            "char_count": len(chunk_text),
                        },
                    }
                )
                global_chunk_idx += 1

        return chunks

    def chunk_text(
        self,
        text: str,
        filename: str = "document.txt",
        doc_id: str = "doc_1",
        page_number: int = 1,
    ) -> List[Dict[str, Any]]:
        """Convenience method to chunk raw text directly.

        Args:
            text: Raw string text.
            filename: Name of the originating file.
            doc_id: Unique identifier for the document.
            page_number: Page number label (default 1).

        Returns:
            List of chunk dicts matching split_pages output structure.
        """
        pages = [{"text": text, "page_number": page_number, "filename": filename}]
        return self.split_pages(pages, doc_id=doc_id)

    def _chunk_single_text(self, text: str) -> List[str]:
        """Split a continuous string into chunks of ~chunk_size with chunk_overlap."""
        text = text.strip()
        if not text:
            return []

        if len(text) <= self.chunk_size:
            return [text]

        chunks: List[str] = []
        start = 0
        text_len = len(text)
        step = self.chunk_size - self.chunk_overlap

        while start < text_len:
            end = min(start + self.chunk_size, text_len)

            # If we're not at the very end, try to find a natural break near the end of the window
            if end < text_len:
                # Search for preferred break points in the last 20% of the chunk
                search_start = max(start + int(self.chunk_size * 0.75), start)
                snippet = text[search_start:end]

                break_offset = -1
                for delimiter in ("\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " "):
                    pos = snippet.rfind(delimiter)
                    if pos != -1:
                        # Found delimiter; split right after it
                        break_offset = search_start + pos + len(delimiter)
                        break

                if break_offset != -1 and break_offset > start:
                    end = break_offset

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Advance window
            if end >= text_len:
                break

            # Calculate next start position
            next_start = end - self.chunk_overlap
            # Ensure forward progress
            if next_start <= start:
                next_start = start + step

            start = next_start

        return chunks
