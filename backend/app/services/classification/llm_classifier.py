from __future__ import annotations
import logging

from pydantic import BaseModel

from app.cdm.models import ParsedDocument
from app.services.classification.assembler import (
    BatchPageResult, assemble_regions, resolve_page_statuses,
)
from app.services.classification.port import ClassificationPort, ClassificationResult
from app.services.classification.serializer import build_batches, serialize_pages
from app.services.llm.port import LLMPort
from app.services.llm.types import LLMConfig
from app.services.classification.prompt_constants import (
    DEFAULT_SYSTEM_PROMPT as _DEFAULT_SYSTEM_PROMPT,
    _REQUIRED_FORMAT,
)

logger = logging.getLogger(__name__)


class _PageResult(BaseModel):
    page: int
    labels: dict[str, str]


class _BatchLLMResponse(BaseModel):
    pages: list[_PageResult]


class LLMClassifier:
    def __init__(
        self,
        adapter: LLMPort,
        provider: str,
        model: str,
        batch_size: int = 10,
        batch_overlap: int = 3,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> None:
        self.adapter = adapter
        self.provider = provider
        self.model = model
        self.batch_size = batch_size
        self.batch_overlap = batch_overlap
        if system_prompt:
            self.system_prompt = system_prompt + "\n\n" + _REQUIRED_FORMAT
        else:
            self.system_prompt = _DEFAULT_SYSTEM_PROMPT
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def classify(
        self, doc: ParsedDocument, labels: list[str]
    ) -> ClassificationResult:
        config = LLMConfig(
            provider=self.provider,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            structured_output_mode="json_mode",
        )
        labels_str = ", ".join(labels)
        batches = build_batches(doc.page_count, self.batch_size, self.batch_overlap)
        all_batch_results: list[list[BatchPageResult]] = []
        total_input = 0
        total_output = 0

        for batch_start, batch_end in batches:
            serialized = serialize_pages(doc, batch_start, batch_end)
            messages = [
                {"role": "system", "content": self.system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Labels to identify: {labels_str}\n\n"
                        f"Document pages:\n{serialized}"
                    ),
                },
            ]
            result = await self.adapter.complete(messages, config)
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
        return ClassificationResult(
            regions=regions, input_tokens=total_input, output_tokens=total_output,
        )
