"""Document extraction adapter.

Uses LlamaIndex SimpleDirectoryReader for PDFs and pytesseract + Pillow for images.
"""
import time
from pathlib import Path

from llama_index.core import SimpleDirectoryReader

from app.ports.document_processing import ExtractionResult

IMAGE_MIME_TYPES = {"image/jpeg", "image/png"}


class LlamaIndexExtractor:
    """DocumentExtractor implementation.

    Routes PDFs to LlamaIndex SimpleDirectoryReader and images to pytesseract OCR.
    """

    SUPPORTED_MIME_TYPES = {
        "application/pdf",
        *IMAGE_MIME_TYPES,
    }

    def supports_mime_type(self, mime_type: str) -> bool:
        """Check if this extractor supports the given MIME type."""
        return mime_type in self.SUPPORTED_MIME_TYPES

    async def extract(self, file_path: str, mime_type: str) -> ExtractionResult:
        """Extract text from a document.

        Routes to the appropriate extraction method based on MIME type.

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

        if mime_type in IMAGE_MIME_TYPES:
            return self._extract_image(file_path_obj)

        return self._extract_pdf(file_path_obj)

    def _extract_pdf(self, file_path: Path) -> ExtractionResult:
        """Extract text from a PDF using LlamaIndex SimpleDirectoryReader."""
        start_time = time.time()

        try:
            reader = SimpleDirectoryReader(
                input_files=[str(file_path)],
                filename_as_id=True
            )
            documents = reader.load_data()

            if not documents:
                raise Exception("No content extracted from document")

            pages_with_markers = []
            page_boundaries = []
            current_offset = 0
            for i, doc in enumerate(documents, 1):
                page_text = f"[Page {i}]\n{doc.text}"
                pages_with_markers.append(page_text)
                end_offset = current_offset + len(page_text)
                page_boundaries.append({"page": i, "start_char": current_offset, "end_char": end_offset})
                current_offset = end_offset + 2  # +2 for "\n\n" separator

            combined_text = "\n\n".join(pages_with_markers)
            page_count = len(documents)
            duration_ms = int((time.time() - start_time) * 1000)

            return ExtractionResult(
                text=combined_text,
                page_count=page_count,
                metadata={
                    "extraction_method": "llamaindex",
                    "extraction_version": "0.1.0",
                    "extracted_at": time.time(),
                    "duration_ms": duration_ms,
                    "token_count": len(combined_text.split()),
                },
                page_boundaries=page_boundaries,
            )

        except Exception as e:
            raise Exception(f"Failed to extract text from {file_path}: {e}") from e

    def _extract_image(self, file_path: Path) -> ExtractionResult:
        """Extract text from an image using pytesseract OCR."""
        try:
            import pytesseract
            from PIL import Image
        except ImportError as e:
            raise ImportError(
                "Image OCR requires pytesseract and Pillow. "
                "Install them with: pip install pytesseract Pillow"
            ) from e

        start_time = time.time()

        try:
            image = Image.open(file_path)
            if image.mode != "RGB":
                image = image.convert("RGB")

            width, height = image.size
            text = pytesseract.image_to_string(image).strip()
            duration_ms = int((time.time() - start_time) * 1000)

            page_text = f"[Page 1]\n{text}"

            return ExtractionResult(
                text=page_text,
                page_count=1,
                metadata={
                    "extraction_method": "pytesseract",
                    "extraction_version": "0.1.0",
                    "extracted_at": time.time(),
                    "duration_ms": duration_ms,
                    "token_count": len(text.split()),
                    "image_width": width,
                    "image_height": height,
                },
                page_boundaries=[{"page": 1, "start_char": 0, "end_char": len(page_text)}],
            )

        except Exception as e:
            raise Exception(f"Failed to extract text from image {file_path}: {e}") from e
