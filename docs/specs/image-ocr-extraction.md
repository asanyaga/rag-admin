# Image OCR Extraction (Simple Parser)

## Problem

The simple parser only supports PDFs. Image uploads (JPEG, PNG) are gated behind LlamaParse, which requires an external API key. Users should be able to upload and extract text from images using the simple parser path with local OCR.

## Approach

Add pytesseract + Pillow as an image extraction path in `LlamaIndexExtractor`. No new classes or abstractions — just a second method alongside the existing PDF path.

### Dependencies

- `Pillow` (Python)
- `pytesseract` (Python)
- `tesseract-ocr` (system package — apt/apk)

### Backend Changes

**`app/adapters/llamaindex/extractor.py`**

- Add `image/jpeg`, `image/png` to `SUPPORTED_MIME_TYPES`
- Add `_extract_image(file_path) -> ExtractionResult` method:
  - Open with Pillow, convert to RGB
  - Run `pytesseract.image_to_string(image)`
  - Return `ExtractionResult` with `page_count=1`, single page boundary, extraction metadata
- Update `extract()` to route image MIME types to `_extract_image`, PDFs to existing path

**`pyproject.toml`**

- Add `Pillow` and `pytesseract` to dependencies

**`Dockerfile`**

- Add `tesseract-ocr` to system packages

### Frontend Changes

**`DocumentUploadZone.tsx`**

- Accept image types (JPEG, PNG) for both `simple` and `llamaparse` parser selections
- Update help text to reflect image support

### No Changes Needed

- `ExtractionResult` dataclass — images fit the existing contract (text + page_count=1)
- Document model/schema — `source_metadata.mime_type` already captures file type
- Storage layer — already stores any file type
- Background processing flow — already calls `extract()` generically

## Testing

- Unit test: `_extract_image` with a test image containing known text
- Unit test: `extract()` routes correctly by MIME type
- Integration test: upload JPEG via API, verify status transitions to `ready` with extracted text
- Edge cases: image with no text returns empty string, corrupt image raises clear error

## Risks

| Risk | Mitigation |
|------|------------|
| Tesseract not installed at runtime | Check on startup or first use, raise clear error |
| Poor OCR quality on photos/screenshots | Document that OCR works best on scanned documents; LlamaParse remains available for complex images |
| Large images slow to process | Pillow can downscale before OCR if needed (future optimization) |
