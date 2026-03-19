"""LlamaExtract adapter using the llama-cloud SDK."""
import time
from typing import Any

from llama_cloud import AsyncLlamaCloud

from app.ports.data_extraction import DataExtractor, ExtractionOutput


class LlamaExtractAdapter(DataExtractor):
    """LlamaExtract adapter using the llama-cloud SDK.

    Uploads a file to LlamaCloud and runs structured extraction against a JSON Schema.
    """

    def __init__(self, api_key: str | None = None):
        self.client = AsyncLlamaCloud(api_key=api_key) if api_key else AsyncLlamaCloud()

    @property
    def extractor_type(self) -> str:
        return "llamaextract"

    async def extract(
        self,
        file_path: str,
        schema: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> ExtractionOutput:
        """Extract structured data using LlamaExtract API.

        1. Upload file to LlamaCloud
        2. Run extraction with schema and config
        3. Return structured data and metadata
        """
        config = config or {}
        start_time = time.time()

        # Upload file for extraction
        with open(file_path, "rb") as f:
            file_obj = await self.client.files.create(file=f, purpose="extract")

        # Build extraction config
        extraction_config: dict[str, Any] = {
            "extraction_mode": config.get("extraction_mode", "MULTIMODAL"),
            "extraction_target": config.get("extraction_target", "PER_DOC"),
        }
        if "cite_sources" in config:
            extraction_config["cite_sources"] = config["cite_sources"]
        if "use_reasoning" in config:
            extraction_config["use_reasoning"] = config["use_reasoning"]
        if "confidence_scores" in config:
            extraction_config["confidence_scores"] = config["confidence_scores"]
        if "page_range" in config:
            extraction_config["page_range"] = config["page_range"]

        # Run extraction (blocking call, handles polling internally)
        result = await self.client.extraction.extract(
            file_id=file_obj.id,
            data_schema=schema,
            config=extraction_config,
        )

        latency_ms = int((time.time() - start_time) * 1000)

        return ExtractionOutput(
            structured_data=result.data if hasattr(result, "data") else {},
            extraction_metadata=(
                result.extraction_metadata
                if hasattr(result, "extraction_metadata")
                else None
            ),
            metadata={
                "latency_ms": latency_ms,
                "file_id": str(file_obj.id),
            },
        )
