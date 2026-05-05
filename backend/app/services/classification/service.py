# backend/app/services/classification/service.py
from __future__ import annotations
import logging
import time
from uuid import UUID

from pydantic import BaseModel

from app.cdm.classification import ClassifiedRegion
from app.cdm.models import ParsedDocument
from app.services.classification.assembler import (
    BatchPageResult,
    assemble_regions,
    resolve_page_statuses,
)
from app.services.classification.serializer import build_batches, serialize_pages
from app.services.llm.registry import LLMRegistry
from app.services.llm.types import LLMConfig

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a document classifier. Analyze the document pages provided and determine which labels apply to each page.

For each label, classify each page as:
- "start": this page begins a section matching this label
- "continue": this page continues a section from a previous page
- "none": this page does not contain this label

Return ONLY valid JSON in this exact format:
{
  "pages": [
    {"page": <page_index>, "labels": {"<label>": "start"|"continue"|"none", ...}},
    ...
  ]
}

Include every page index present in the document content.\
"""


class _PageResult(BaseModel):
    page: int
    labels: dict[str, str]


class _BatchLLMResponse(BaseModel):
    pages: list[_PageResult]


class ClassificationService:
    def __init__(self, repo: object, llm_registry: LLMRegistry) -> None:
        self.repo = repo
        self.llm_registry = llm_registry

    async def execute(
        self,
        run_id: UUID,
        doc: ParsedDocument,
        labels: list[str],
        llm_provider: str,
        llm_model: str,
        batch_size: int,
        batch_overlap: int,
    ) -> None:
        await self.repo.update_status(run_id=run_id, status="running")
        start = time.monotonic()
        total_input = 0
        total_output = 0

        try:
            adapter = self.llm_registry.get(llm_provider)
            config = LLMConfig(
                provider=llm_provider,
                model=llm_model,
                temperature=0.0,
                max_tokens=4096,
                json_mode=True,
            )
            labels_str = ", ".join(labels)
            batches = build_batches(doc.page_count, batch_size, batch_overlap)
            all_batch_results: list[list[BatchPageResult]] = []

            for batch_start, batch_end in batches:
                serialized = serialize_pages(doc, batch_start, batch_end)
                messages = [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Labels to identify: {labels_str}\n\n"
                            f"Document pages:\n{serialized}"
                        ),
                    },
                ]
                result = await adapter.complete(messages, config)
                total_input += result.usage.prompt_tokens
                total_output += result.usage.completion_tokens

                parsed = _BatchLLMResponse.model_validate_json(result.content)
                batch_page_results = [
                    BatchPageResult(
                        page=p.page,
                        label_statuses=p.labels,
                        batch_start=batch_start,
                        batch_end=batch_end,
                    )
                    for p in parsed.pages
                ]
                all_batch_results.append(batch_page_results)

            resolved = resolve_page_statuses(all_batch_results)
            regions = assemble_regions(resolved, labels, doc)

            await self.repo.save_regions(run_id=run_id, regions=regions)
            duration_ms = int((time.monotonic() - start) * 1000)
            await self.repo.update_completed(
                run_id=run_id,
                input_tokens=total_input,
                output_tokens=total_output,
                duration_ms=duration_ms,
            )

        except Exception as exc:
            logger.exception("Classification run %s failed", run_id)
            await self.repo.update_status(run_id=run_id, status="failed", error=str(exc))
            raise
