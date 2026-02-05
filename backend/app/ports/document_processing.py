"""Document processing port interface."""
from dataclasses import dataclass
from typing import Protocol


@dataclass
class ExtractionResult:
    """Result of document text extraction."""
    text: str
    page_count: int
    metadata: dict


class DocumentExtractor(Protocol):
    """Port interface for document text extraction.

    Implementations can use LlamaIndex, PyPDF2, Unstructured, etc.
    """

    async def extract(self, file_path: str, mime_type: str) -> ExtractionResult:
        """Extract text from a document file.

        Args:
            file_path: Path to the document file
            mime_type: MIME type of the document (e.g., "application/pdf")

        Returns:
            ExtractionResult containing extracted text with page markers,
            page count, and extraction metadata

        Raises:
            ValueError: If file type is not supported
            IOError: If file cannot be read
            Exception: If extraction fails
        """
        ...

    def supports_mime_type(self, mime_type: str) -> bool:
        """Check if this extractor supports the given MIME type.

        Args:
            mime_type: MIME type to check

        Returns:
            True if supported, False otherwise
        """
        ...
