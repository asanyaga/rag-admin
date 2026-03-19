"""Tests for LlamaIndexExtractor (PDF + image OCR)."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.adapters.llamaindex.extractor import LlamaIndexExtractor


class TestSupportsMimeType:
    def test_supports_pdf(self):
        extractor = LlamaIndexExtractor()
        assert extractor.supports_mime_type("application/pdf") is True

    def test_supports_jpeg(self):
        extractor = LlamaIndexExtractor()
        assert extractor.supports_mime_type("image/jpeg") is True

    def test_supports_png(self):
        extractor = LlamaIndexExtractor()
        assert extractor.supports_mime_type("image/png") is True

    def test_rejects_unsupported(self):
        extractor = LlamaIndexExtractor()
        assert extractor.supports_mime_type("text/plain") is False
        assert extractor.supports_mime_type("application/zip") is False


class TestExtractRouting:
    async def test_rejects_unsupported_mime_type(self):
        extractor = LlamaIndexExtractor()
        with pytest.raises(ValueError, match="Unsupported MIME type"):
            await extractor.extract("/some/file.txt", "text/plain")

    async def test_rejects_missing_file(self):
        extractor = LlamaIndexExtractor()
        with pytest.raises(IOError, match="File not found"):
            await extractor.extract("/nonexistent/file.png", "image/png")

    @patch.object(LlamaIndexExtractor, "_extract_image")
    async def test_routes_jpeg_to_image_extractor(self, mock_extract, tmp_path):
        img_file = tmp_path / "test.jpg"
        img_file.write_bytes(b"fake")
        mock_extract.return_value = MagicMock()

        extractor = LlamaIndexExtractor()
        await extractor.extract(str(img_file), "image/jpeg")
        mock_extract.assert_called_once()

    @patch.object(LlamaIndexExtractor, "_extract_image")
    async def test_routes_png_to_image_extractor(self, mock_extract, tmp_path):
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"fake")
        mock_extract.return_value = MagicMock()

        extractor = LlamaIndexExtractor()
        await extractor.extract(str(img_file), "image/png")
        mock_extract.assert_called_once()

    @patch.object(LlamaIndexExtractor, "_extract_pdf")
    async def test_routes_pdf_to_pdf_extractor(self, mock_extract, tmp_path):
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"fake")
        mock_extract.return_value = MagicMock()

        extractor = LlamaIndexExtractor()
        await extractor.extract(str(pdf_file), "application/pdf")
        mock_extract.assert_called_once()


class TestExtractImage:
    def _make_extractor_with_mocks(self, mock_image, mock_tess):
        """Patch the lazy imports by injecting mocks into _extract_image."""
        import types

        extractor = LlamaIndexExtractor()
        original = extractor._extract_image

        def patched_extract_image(file_path):
            import sys
            # Temporarily inject mock modules so the local imports resolve to them
            mock_pil_mod = types.ModuleType("PIL")
            mock_pil_image = types.ModuleType("PIL.Image")
            mock_pil_image.open = mock_image.open
            mock_pil_mod.Image = mock_pil_image
            sys.modules["PIL"] = mock_pil_mod
            sys.modules["PIL.Image"] = mock_pil_image

            mock_tess_mod = types.ModuleType("pytesseract")
            mock_tess_mod.image_to_string = mock_tess.image_to_string
            sys.modules["pytesseract"] = mock_tess_mod

            try:
                return original(file_path)
            finally:
                sys.modules.pop("PIL", None)
                sys.modules.pop("PIL.Image", None)
                sys.modules.pop("pytesseract", None)

        extractor._extract_image = patched_extract_image
        return extractor

    async def test_extracts_text_from_image(self, tmp_path):
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"fake")

        mock_img_instance = MagicMock()
        mock_img_instance.mode = "RGB"
        mock_img_instance.size = (800, 600)
        mock_pil = MagicMock()
        mock_pil.open.return_value = mock_img_instance
        mock_tess = MagicMock()
        mock_tess.image_to_string.return_value = "Hello World"

        extractor = self._make_extractor_with_mocks(mock_pil, mock_tess)
        result = extractor._extract_image(Path(img_file))

        assert result.text == "[Page 1]\nHello World"
        assert result.page_count == 1
        assert result.metadata["extraction_method"] == "pytesseract"
        assert result.metadata["image_width"] == 800
        assert result.metadata["image_height"] == 600
        assert result.page_boundaries == [{"page": 1, "start_char": 0, "end_char": len("[Page 1]\nHello World")}]

    async def test_converts_non_rgb_image(self, tmp_path):
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"fake")

        mock_img_instance = MagicMock()
        mock_img_instance.mode = "RGBA"
        mock_converted = MagicMock()
        mock_converted.size = (100, 100)
        mock_img_instance.convert.return_value = mock_converted
        mock_pil = MagicMock()
        mock_pil.open.return_value = mock_img_instance
        mock_tess = MagicMock()
        mock_tess.image_to_string.return_value = "text"

        extractor = self._make_extractor_with_mocks(mock_pil, mock_tess)
        extractor._extract_image(Path(img_file))

        mock_img_instance.convert.assert_called_once_with("RGB")
        mock_tess.image_to_string.assert_called_once_with(mock_converted)

    async def test_empty_text_from_image(self, tmp_path):
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"fake")

        mock_img_instance = MagicMock()
        mock_img_instance.mode = "RGB"
        mock_img_instance.size = (100, 100)
        mock_pil = MagicMock()
        mock_pil.open.return_value = mock_img_instance
        mock_tess = MagicMock()
        mock_tess.image_to_string.return_value = "   "

        extractor = self._make_extractor_with_mocks(mock_pil, mock_tess)
        result = extractor._extract_image(Path(img_file))

        assert result.text == "[Page 1]\n"
        assert result.metadata["token_count"] == 0
