"""Document loader service.

Extracts text from PDF (using pypdf) and .txt files while retaining
document- and page-level metadata.
"""

import io
from pathlib import Path
from typing import List, Dict, Any, Union, Optional
import pypdf


class DocumentLoader:
    """Service for loading document files and extracting text with page numbers."""

    SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}

    @classmethod
    def is_supported(cls, filename: str) -> bool:
        """Check if the given filename has a supported extension."""
        suffix = Path(filename).suffix.lower()
        return suffix in cls.SUPPORTED_EXTENSIONS

    def load_bytes(self, file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
        """Extract text from in-memory file bytes.

        Args:
            file_bytes: Raw binary content of the file.
            filename: Original name of the uploaded file.

        Returns:
            List of page dictionaries:
            [
                {
                    "text": "Extracted text content...",
                    "page_number": 1,
                    "filename": "annual_report.pdf",
                },
                ...
            ]

        Raises:
            ValueError: If file format is unsupported or contains no extractable text.
        """
        suffix = Path(filename).suffix.lower()

        if suffix == ".pdf":
            return self._load_pdf(file_bytes, filename)
        elif suffix in {".txt", ".md"}:
            return self._load_text(file_bytes, filename)
        else:
            raise ValueError(
                f"Unsupported file format '{suffix}'. Allowed formats: {', '.join(sorted(self.SUPPORTED_EXTENSIONS))}"
            )

    def load_path(self, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """Extract text from a file on the local filesystem."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        file_bytes = path.read_bytes()
        return self.load_bytes(file_bytes, path.name)

    def load_file(
        self,
        file_source: Union[str, Path, io.BytesIO, bytes],
        filename: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Extract text from a file path, BytesIO stream, or raw bytes."""
        if isinstance(file_source, (str, Path)):
            return self.load_path(file_source)
        elif isinstance(file_source, io.BytesIO):
            return self.load_bytes(file_source.getvalue(), filename or "document.pdf")
        elif isinstance(file_source, bytes):
            return self.load_bytes(file_source, filename or "document.pdf")
        raise TypeError(f"Unsupported file source type: {type(file_source)}")

    def _load_pdf(self, file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
        """Parse PDF binary content using pypdf and extract page texts."""
        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        except Exception as e:
            raise ValueError(f"Corrupt or invalid PDF file: {str(e)}")

        pages: List[Dict[str, Any]] = []
        total_pages = len(reader.pages)

        if total_pages == 0:
            raise ValueError("The provided PDF has no pages.")

        for page_idx, page in enumerate(reader.pages):
            page_num = page_idx + 1
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""

            cleaned_text = page_text.strip()
            # Only add pages that have non-whitespace content
            if cleaned_text:
                pages.append(
                    {
                        "text": cleaned_text,
                        "page_number": page_num,
                        "filename": filename,
                    }
                )

        if not pages:
            raise ValueError(
                f"No extractable text found in '{filename}'. Scanned or image-only PDFs require OCR."
            )

        return pages

    def _load_text(self, file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
        """Parse plain text or markdown content with encoding fallback."""
        text = ""
        # Try UTF-8 first, fallback to utf-8-sig and latin-1
        for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                text = file_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        cleaned_text = text.strip()
        if not cleaned_text:
            raise ValueError(f"The text file '{filename}' is empty.")

        return [
            {
                "text": cleaned_text,
                "page_number": 1,
                "filename": filename,
            }
        ]
