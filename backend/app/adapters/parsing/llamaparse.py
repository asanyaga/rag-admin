"""LlamaParse adapter using the llama-cloud SDK >= 1.0."""
import time
from typing import Any

from llama_cloud import AsyncLlamaCloud

from app.ports.document_parsing import (
    DocumentParser,
    ParseOutput,
    ParserType,
    ParseFidelity,
)


class LlamaParseAdapter(DocumentParser):
    """LlamaParse adapter using the llama-cloud SDK >= 1.0.

    Uses client.parsing.parse() which handles upload + polling internally.
    """

    def __init__(self, api_key: str | None = None):
        self.client = AsyncLlamaCloud(api_key=api_key) if api_key else AsyncLlamaCloud()

    @property
    def parser_type(self) -> ParserType:
        return ParserType.LLAMAPARSE

    @property
    def default_fidelity(self) -> ParseFidelity:
        return ParseFidelity.MARKDOWN

    def supported_file_types(self) -> list[str]:
        return [
            "application/pdf",
            "image/jpeg", "image/png", "image/gif", "image/bmp", "image/tiff", "image/webp",
        ]

    async def parse(self, file_path: str, config: dict[str, Any] | None = None) -> ParseOutput:
        """Parse a document using LlamaParse API (v1.0+ SDK).

        Uses client.parsing.parse() which uploads the file and polls internally.
        """
        config = config or {}
        tier = config.get("tier", "agentic")
        requested_expand = config.get("expand", ["markdown", "text"])

        # Build expand list based on tier
        if tier == "fast":
            expand = ["text"]
        else:
            expand = [e for e in requested_expand if e in ["text", "markdown", "items", "metadata"]]
            if not expand:
                expand = ["text"]

        start_time = time.time()

        # parse() handles upload + polling internally and returns the full result
        result = await self.client.parsing.parse(
            upload_file=file_path,
            tier=tier,
            version=config.get("version", "latest"),
            expand=expand,
        )

        latency_ms = int((time.time() - start_time) * 1000)

        # Extract text
        raw_text = ""
        if hasattr(result, "text") and result.text:
            raw_text_parts = []
            for page in result.text.pages:
                raw_text_parts.append(f"[Page {page.page_number}]\n{page.text}")
            raw_text = "\n\n".join(raw_text_parts)

        # Extract markdown
        markdown_text = None
        pages: list[dict[str, Any]] = []
        if hasattr(result, "markdown") and result.markdown:
            md_parts = []
            for page in result.markdown.pages:
                if page.success:
                    md_parts.append(page.markdown)
                    pages.append({
                        "page_number": page.page_number,
                        "markdown": page.markdown,
                    })
            markdown_text = "\n\n".join(md_parts) if md_parts else None

        # Also try markdown_full if available (single-string result)
        if not markdown_text and hasattr(result, "markdown_full"):
            markdown_text = result.markdown_full

        # Also try text_full
        if not raw_text and hasattr(result, "text_full"):
            raw_text = result.text_full or ""

        # Extract structured items
        document_structure = None
        if hasattr(result, "items") and result.items:
            items = []
            for page in result.items.pages:
                if page.success:
                    for item in page.items:
                        items.append({
                            "type": getattr(item, "type", None),
                            "value": getattr(item, "value", ""),
                            "md": getattr(item, "md", ""),
                            "page": page.page_number,
                            "bbox": item.bbox[0].__dict__ if getattr(item, "bbox", None) else None,
                        })
            if items:
                document_structure = {"items": items}

        # Determine fidelity
        if document_structure:
            fidelity = "layout_json"
        elif markdown_text:
            fidelity = "markdown"
        else:
            fidelity = "text"

        # Fallback: if no raw_text but have markdown, use markdown as text
        if not raw_text and markdown_text:
            raw_text = markdown_text

        job_id = result.job.id if hasattr(result, "job") else None

        return ParseOutput(
            raw_text=raw_text,
            markdown=markdown_text,
            pages=pages if pages else None,
            document_structure=document_structure,
            fidelity=fidelity,
            parser_type="llamaparse",
            parser_config={"tier": tier, "expand": expand, "version": config.get("version", "latest")},
            metadata={
                "llamaparse_job_id": job_id,
                "latency_ms": latency_ms,
                "page_count": len(pages) if pages else 0,
            },
        )
