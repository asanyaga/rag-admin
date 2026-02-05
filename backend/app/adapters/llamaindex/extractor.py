"""LlamaIndex document extraction adapter."""
import time
from pathlib import Path

from llama_index.core import SimpleDirectoryReader
from llama_index.core.schema import Document as LlamaDocument

from app.ports.document_processing import ExtractionResult


class LlamaIndexExtractor:
    """LlamaIndex implementation of DocumentExtractor.

    Uses LlamaIndex SimpleDirectoryReader for document parsing.
    """

    # Supported MIME types
    SUPPORTED_MIME_TYPES = {
        "application/pdf",
    }

    def supports_mime_type(self, mime_type: str) -> bool:
        """Check if this extractor supports the given MIME type.

        Args:
            mime_type: MIME type to check

        Returns:
            True if supported, False otherwise
        """
        return mime_type in self.SUPPORTED_MIME_TYPES

    async def extract(self, file_path: str, mime_type: str) -> ExtractionResult:
        """Extract text from a document using LlamaIndex.

        Args:
            file_path: Path to the document file
            mime_type: MIME type of the document

        Returns:
            ExtractionResult containing extracted text with page markers

        Raises:
            ValueError: If file type is not supported
            IOError: If file cannot be read
            Exception: If extraction fails
        """
        if not self.supports_mime_type(mime_type):
            raise ValueError(f"Unsupported MIME type: {mime_type}")

        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise IOError(f"File not found: {file_path}")

        start_time = time.time()

        try:
            # Use SimpleDirectoryReader to load the document
            # It automatically handles PDFs and extracts text page by page
            reader = SimpleDirectoryReader(
                input_files=[str(file_path_obj)],
                filename_as_id=True
            )
            documents = reader.load_data()

            if not documents:
                raise Exception("No content extracted from document")

            # Add page markers and combine text
            pages_with_markers = []
            for i, doc in enumerate(documents, 1):
                pages_with_markers.append(f"[Page {i}]\n{doc.text}")

            combined_text = "\n\n".join(pages_with_markers)
            page_count = len(documents)

            # Calculate extraction metrics
            duration_ms = int((time.time() - start_time) * 1000)
            token_count = len(combined_text.split())  # Rough token estimate

            metadata = {
                "extraction_method": "llamaindex",
                "extraction_version": "0.1.0",
                "extracted_at": time.time(),
                "duration_ms": duration_ms,
                "token_count": token_count,
            }

            return ExtractionResult(
                text=combined_text,
                page_count=page_count,
                metadata=metadata
            )

        except Exception as e:
            raise Exception(f"Failed to extract text from {file_path}: {e}") from e
