"""Service for auto-generating golden set queries from documents using LLMs."""
import json
import logging
import math
from uuid import UUID

from app.models.golden_set import GenerationStatus, SourceMethod, ReviewStatus
from app.repositories.golden_set_repository import GoldenSetRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.provider_key_repository import ProviderKeyRepository
from app.services.llm.types import LLMConfig
from app.services.llm.factory import create_adapter
from app.services.llm.port import LLMPort
from app.services.exceptions import NotFoundError, ValidationError
from app.utils.encryption import decrypt

logger = logging.getLogger(__name__)

DEFAULT_GENERATION_SYSTEM_PROMPT = (
    "You are an expert at creating evaluation queries for document retrieval systems. "
    "Given document content, you generate realistic search queries that a user might ask, "
    "along with the specific pages that contain the answer.\n\n"
    "You MUST respond with valid JSON in this exact format:\n"
    '{"queries": [\n'
    '  {\n'
    '    "query": "the search query text",\n'
    '    "question_type": "factual|comparison|summarization",\n'
    '    "relevant_pages": [page_numbers],\n'
    '    "reasoning": "brief explanation of why these pages answer the query"\n'
    '  }\n'
    ']}\n\n'
    "Rules:\n"
    "- Each query must be answerable from the provided pages only\n"
    "- Page numbers must be from the provided page range\n"
    "- Queries should be diverse and realistic\n"
    "- Each query should reference 1-3 specific pages\n"
    "- Do not create questions that require external knowledge"
)

# Page windowing constants
WINDOW_SIZE = 5
WINDOW_OVERLAP = 1


class GoldenSetGenerationService:
    """Orchestrates auto-generation of golden set queries from documents."""

    def __init__(
        self,
        golden_set_repo: GoldenSetRepository,
        document_repo: DocumentRepository,
        provider_key_repo: ProviderKeyRepository,
    ):
        self.gs_repo = golden_set_repo
        self.doc_repo = document_repo
        self.provider_key_repo = provider_key_repo

    async def trigger_generation(
        self,
        gs_id: UUID,
        project_id: UUID,
        user_id: UUID,
        document_ids: list[UUID],
        llm_provider: str,
        llm_model: str,
        queries_per_document: int,
        question_types: list[str],
        temperature: float,
        system_prompt: str | None = None,
    ) -> None:
        """Validate inputs, store config, set status=pending."""
        gs = await self.gs_repo.get_by_id(gs_id, project_id)
        if not gs:
            raise NotFoundError(f"Golden set {gs_id} not found")

        if gs.generation_status in (GenerationStatus.pending, GenerationStatus.generating):
            raise ValidationError("Generation is already in progress")

        # Validate API key exists
        key = await self.provider_key_repo.get_for_provider(
            user_id=user_id, provider=llm_provider, project_id=project_id
        )
        if not key:
            raise ValidationError(f"No API key configured for provider '{llm_provider}'")

        # Store generation config
        config = {
            "document_ids": [str(d) for d in document_ids],
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "queries_per_document": queries_per_document,
            "question_types": question_types,
            "temperature": temperature,
            "system_prompt": system_prompt,
        }
        await self.gs_repo.set_generation_config(gs_id, project_id, config)
        await self.gs_repo.update_generation_status(
            gs_id,
            GenerationStatus.pending,
            progress={"totalWindows": 0, "completedWindows": 0, "errorMessage": None},
        )

    async def execute_generation(
        self,
        gs_id: UUID,
        project_id: UUID,
        user_id: UUID,
    ) -> None:
        """Background task entry point: generate queries from documents."""
        try:
            # Load golden set and config
            gs = await self.gs_repo.get_by_id(gs_id, project_id)
            if not gs or not gs.generation_config:
                logger.error("Golden set %s not found or no config", gs_id)
                return

            config = gs.generation_config
            document_ids = [UUID(d) for d in config["document_ids"]]
            llm_provider = config["llm_provider"]
            llm_model = config["llm_model"]
            queries_per_document = config["queries_per_document"]
            question_types = config["question_types"]
            temperature = config["temperature"]
            system_prompt = config.get("system_prompt")

            # Get API key
            key_record = await self.provider_key_repo.get_for_provider(
                user_id=user_id, provider=llm_provider, project_id=project_id
            )
            if not key_record:
                await self.gs_repo.update_generation_status(
                    gs_id, GenerationStatus.failed,
                    progress={"totalWindows": 0, "completedWindows": 0, "errorMessage": "No API key found"},
                )
                return

            api_key = decrypt(key_record.api_key_encrypted)
            adapter = create_adapter(llm_provider, api_key, key_record.base_url)

            # Load documents and build windows
            all_windows: list[dict] = []
            for doc_id in document_ids:
                doc = await self.doc_repo.get_by_id_unscoped(doc_id)
                if not doc or not doc.extracted_text:
                    logger.warning("Document %s not found or has no text, skipping", doc_id)
                    continue

                page_boundaries = (doc.processing_metadata or {}).get("page_boundaries", [])
                windows = self._build_page_windows(
                    doc_id=doc_id,
                    extracted_text=doc.extracted_text,
                    page_boundaries=page_boundaries,
                    doc_title=doc.title,
                )
                for w in windows:
                    w["queries_per_window"] = math.ceil(
                        queries_per_document / max(len(windows), 1)
                    )
                all_windows.extend(windows)

            total_windows = len(all_windows)
            await self.gs_repo.update_generation_status(
                gs_id, GenerationStatus.generating,
                progress={"totalWindows": total_windows, "completedWindows": 0, "errorMessage": None},
            )

            if total_windows == 0:
                await self.gs_repo.update_generation_status(
                    gs_id, GenerationStatus.failed,
                    progress={"totalWindows": 0, "completedWindows": 0, "errorMessage": "No content windows to process"},
                )
                return

            # Process each window
            completed = 0
            errors = 0
            for window in all_windows:
                try:
                    await self._process_window(
                        gs_id=gs_id,
                        window=window,
                        adapter=adapter,
                        llm_model=llm_model,
                        temperature=temperature,
                        question_types=question_types,
                        llm_provider=llm_provider,
                        system_prompt=system_prompt,
                    )
                except Exception as e:
                    logger.error("Error processing window for doc %s: %s", window["doc_id"], e)
                    errors += 1

                completed += 1
                await self.gs_repo.update_generation_status(
                    gs_id, GenerationStatus.generating,
                    progress={"totalWindows": total_windows, "completedWindows": completed, "errorMessage": None},
                )

            # Final status
            final_status = GenerationStatus.completed if errors < total_windows else GenerationStatus.failed
            error_msg = f"{errors} window(s) failed" if errors > 0 else None
            await self.gs_repo.update_generation_status(
                gs_id, final_status,
                progress={"totalWindows": total_windows, "completedWindows": completed, "errorMessage": error_msg},
            )

        except Exception as e:
            logger.exception("Generation failed for golden set %s", gs_id)
            await self.gs_repo.update_generation_status(
                gs_id, GenerationStatus.failed,
                progress={"totalWindows": 0, "completedWindows": 0, "errorMessage": str(e)},
            )

    async def _process_window(
        self,
        gs_id: UUID,
        window: dict,
        adapter: LLMPort,
        llm_model: str,
        temperature: float,
        question_types: list[str],
        llm_provider: str = "openai",
        system_prompt: str | None = None,
    ) -> None:
        """Generate queries for a single page window."""
        messages = self._build_generation_prompt(
            page_text=window["text"],
            page_range=window["page_range"],
            doc_title=window["doc_title"],
            queries_count=window["queries_per_window"],
            question_types=question_types,
            system_prompt=system_prompt,
        )

        config = LLMConfig(
            provider=llm_provider,
            model=llm_model,
            temperature=temperature,
            max_tokens=4096,
            structured_output_mode="json_mode",
        )

        result = await adapter.complete(messages, config)
        queries = self._parse_llm_response(result.content, window["page_range"])

        # Store parsed queries
        for q in queries:
            query = await self.gs_repo.add_query_with_metadata(
                golden_set_id=gs_id,
                query_text=q["query"],
                source_method=SourceMethod.auto_generated,
                review_status=ReviewStatus.pending,
                reasoning=q.get("reasoning"),
                question_type=q.get("question_type"),
            )
            # Add source with page locator
            if q.get("relevant_pages"):
                await self.gs_repo.add_source(
                    query_id=query.id,
                    document_id=window["doc_id"],
                    locator={"type": "page", "pages": q["relevant_pages"]},
                )

    def _build_page_windows(
        self,
        doc_id: UUID,
        extracted_text: str,
        page_boundaries: list[dict],
        doc_title: str,
    ) -> list[dict]:
        """Build overlapping page windows from document text.

        page_boundaries is a list of dicts: {"page": 1, "start_char": 0, "end_char": 500}
        """
        if not page_boundaries:
            # No page info — treat entire doc as single window
            return [{
                "doc_id": doc_id,
                "doc_title": doc_title,
                "text": extracted_text,
                "page_range": [1],
            }]

        total_pages = len(page_boundaries)
        windows = []
        step = WINDOW_SIZE - WINDOW_OVERLAP

        for start_idx in range(0, total_pages, step):
            end_idx = min(start_idx + WINDOW_SIZE, total_pages)
            page_range = [page_boundaries[i]["page"] for i in range(start_idx, end_idx)]

            # Extract text for this window using char offsets
            text_start = int(page_boundaries[start_idx]["start_char"])
            text_end = int(page_boundaries[end_idx - 1]["end_char"])
            text = extracted_text[text_start:text_end]

            if text.strip():
                windows.append({
                    "doc_id": doc_id,
                    "doc_title": doc_title,
                    "text": text,
                    "page_range": page_range,
                })

            if end_idx >= total_pages:
                break

        return windows

    def _build_generation_prompt(
        self,
        page_text: str,
        page_range: list[int],
        doc_title: str,
        queries_count: int,
        question_types: list[str],
        system_prompt: str | None = None,
    ) -> list[dict]:
        """Build system + user messages for the LLM."""
        type_desc = ", ".join(question_types)
        page_desc = ", ".join(str(p) for p in page_range)

        system_msg = system_prompt or DEFAULT_GENERATION_SYSTEM_PROMPT

        user_msg = (
            f"Document: {doc_title}\n"
            f"Pages: {page_desc}\n"
            f"Generate {queries_count} queries of type(s): {type_desc}\n\n"
            f"--- Document Content ---\n{page_text[:50000]}"
        )

        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

    def _parse_llm_response(
        self, content: str, valid_pages: list[int]
    ) -> list[dict]:
        """Parse and validate the LLM JSON response."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response as JSON")
            return []

        queries_raw = data.get("queries", [])
        if not isinstance(queries_raw, list):
            return []

        result = []
        for item in queries_raw:
            if not isinstance(item, dict):
                continue
            query_text = item.get("query", "").strip()
            if not query_text:
                continue

            # Filter page refs to valid range
            raw_pages = item.get("relevant_pages", [])
            if not isinstance(raw_pages, list):
                raw_pages = []
            filtered_pages = [p for p in raw_pages if isinstance(p, int) and p in valid_pages]

            if not filtered_pages:
                continue  # Discard entries with no valid page refs

            result.append({
                "query": query_text,
                "question_type": item.get("question_type"),
                "relevant_pages": filtered_pages,
                "reasoning": item.get("reasoning"),
            })

        return result
