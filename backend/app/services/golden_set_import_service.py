"""Service for importing queries into golden sets from CSV/JSON files."""
import csv
import io
import json
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, GoldenSetQuery
from app.models.golden_set import SourceMethod, ReviewStatus


MAX_ROWS = 500
MAX_QUERY_LENGTH = 2000


@dataclass
class ParsedSource:
    document_name: str
    document_id: UUID | None = None
    pages: list[int] = field(default_factory=list)
    resolved: bool = False
    error: str | None = None


@dataclass
class ParsedQuery:
    row: int
    query_text: str
    sources: list[ParsedSource] = field(default_factory=list)
    is_duplicate: bool = False
    existing_query_id: str | None = None


@dataclass
class ParseError:
    row: int
    query_text: str
    error: str


@dataclass
class ParseResult:
    valid_queries: list[ParsedQuery]
    errors: list[ParseError]
    duplicates: list[ParsedQuery]
    total_rows: int


class GoldenSetImportService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def parse_file(
        self,
        file_content: bytes,
        filename: str,
        project_id: UUID,
        golden_set_id: UUID,
    ) -> ParseResult:
        """Parse an uploaded file and return a preview with validation results."""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        if ext == "csv":
            raw_queries = self._parse_csv(file_content)
        elif ext == "json":
            raw_queries = self._parse_json(file_content)
        else:
            raise ValueError(f"Unsupported file format: .{ext}. Use .csv or .json")

        if not raw_queries:
            raise ValueError("File contains no queries")

        if len(raw_queries) > MAX_ROWS:
            raise ValueError(f"File exceeds maximum of {MAX_ROWS} rows")

        # Build doc name lookup for the project
        doc_lookup = await self._build_document_lookup(project_id)

        # Get existing query texts for duplicate detection
        existing_texts = await self._get_existing_query_texts(golden_set_id)

        # Validate and resolve
        valid_queries: list[ParsedQuery] = []
        errors: list[ParseError] = []
        duplicates: list[ParsedQuery] = []
        seen_texts: dict[str, ParsedQuery] = {}  # dedup within file

        for pq in raw_queries:
            text = pq.query_text.strip()

            # Validate query text
            if not text:
                errors.append(ParseError(row=pq.row, query_text="", error="Empty query text"))
                continue
            if len(text) > MAX_QUERY_LENGTH:
                errors.append(ParseError(
                    row=pq.row, query_text=text[:100] + "...",
                    error=f"Query text exceeds {MAX_QUERY_LENGTH} characters"
                ))
                continue

            pq.query_text = text

            # Check duplicate against existing golden set
            normalized = text.lower().strip()
            if normalized in existing_texts:
                pq.is_duplicate = True
                pq.existing_query_id = existing_texts[normalized]
                duplicates.append(pq)
                continue

            # Check duplicate within file — merge sources
            if normalized in seen_texts:
                existing_pq = seen_texts[normalized]
                existing_pq.sources.extend(pq.sources)
                continue

            # Resolve sources
            resolved_sources: list[ParsedSource] = []
            for src in pq.sources:
                doc_name = src.document_name.strip()
                if not doc_name:
                    continue

                doc = doc_lookup.get(doc_name.lower())
                if doc is None:
                    errors.append(ParseError(
                        row=pq.row,
                        query_text=text[:100],
                        error=f"Document not found: '{doc_name}'"
                    ))
                    # Query is still valid, just drop this source
                    continue

                src.document_id = doc["id"]
                src.document_name = doc["name"]
                src.resolved = True

                # Validate pages
                valid_pages = [p for p in src.pages if isinstance(p, int) and p > 0]
                if src.pages and not valid_pages:
                    errors.append(ParseError(
                        row=pq.row,
                        query_text=text[:100],
                        error=f"Invalid page numbers for document '{doc_name}'"
                    ))
                    continue
                src.pages = valid_pages
                resolved_sources.append(src)

            pq.sources = resolved_sources
            valid_queries.append(pq)
            seen_texts[normalized] = pq

        return ParseResult(
            valid_queries=valid_queries,
            errors=errors,
            duplicates=duplicates,
            total_rows=len(raw_queries),
        )

    async def import_queries(
        self,
        golden_set_id: UUID,
        queries: list[dict],
    ) -> list[GoldenSetQuery]:
        """Bulk-create queries with sources in a single transaction."""
        from app.models.golden_set import GoldenSetSource

        # Re-check duplicates at confirm time
        existing_texts = await self._get_existing_query_texts(golden_set_id)

        created: list[GoldenSetQuery] = []
        for q_data in queries:
            text = q_data["query_text"].strip()
            if text.lower().strip() in existing_texts:
                continue  # Skip confirm-time duplicate

            query = GoldenSetQuery(
                golden_set_id=golden_set_id,
                query_text=text,
                source_method=SourceMethod.imported,
                review_status=ReviewStatus.pending,
            )
            self.session.add(query)
            await self.session.flush()  # Get query.id

            for src_data in q_data.get("sources", []):
                source = GoldenSetSource(
                    query_id=query.id,
                    document_id=src_data["document_id"],
                    locator=src_data.get("locator", {}),
                )
                self.session.add(source)

            created.append(query)

        await self.session.commit()
        return created

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_csv(self, content: bytes) -> list[ParsedQuery]:
        """Parse CSV content. Groups rows with the same query_text to merge sources."""
        text = content.decode("utf-8-sig")  # Handle BOM
        reader = csv.DictReader(io.StringIO(text))

        # Normalize headers to lowercase
        if reader.fieldnames is None:
            raise ValueError("CSV file has no headers")

        normalized_fields = {f.strip().lower(): f for f in reader.fieldnames}

        # Find the query_text column
        qt_key = None
        for candidate in ["query_text", "querytext", "query", "question"]:
            if candidate in normalized_fields:
                qt_key = normalized_fields[candidate]
                break
        if qt_key is None:
            raise ValueError(
                "CSV must have a 'query_text' column. "
                f"Found columns: {', '.join(reader.fieldnames)}"
            )

        doc_key = None
        for candidate in ["document_name", "documentname", "document", "doc_name"]:
            if candidate in normalized_fields:
                doc_key = normalized_fields[candidate]
                break

        pages_key = None
        for candidate in ["pages", "page"]:
            if candidate in normalized_fields:
                pages_key = normalized_fields[candidate]
                break

        # Parse rows, grouping by query_text for multi-source support
        queries_by_text: dict[str, ParsedQuery] = {}
        row_num = 0
        for row in reader:
            row_num += 1
            query_text = (row.get(qt_key) or "").strip()
            if not query_text:
                # Will be caught as error in validation
                queries_by_text[f"__empty_{row_num}"] = ParsedQuery(
                    row=row_num, query_text=""
                )
                continue

            source = None
            if doc_key:
                doc_name = (row.get(doc_key) or "").strip()
                if doc_name:
                    pages: list[int] = []
                    if pages_key:
                        pages_str = (row.get(pages_key) or "").strip()
                        if pages_str:
                            pages = self._parse_pages(pages_str)
                    source = ParsedSource(document_name=doc_name, pages=pages)

            normalized = query_text.lower()
            if normalized in queries_by_text:
                if source:
                    queries_by_text[normalized].sources.append(source)
            else:
                pq = ParsedQuery(row=row_num, query_text=query_text)
                if source:
                    pq.sources.append(source)
                queries_by_text[normalized] = pq

        return list(queries_by_text.values())

    def _parse_json(self, content: bytes) -> list[ParsedQuery]:
        """Parse JSON content."""
        try:
            data = json.loads(content.decode("utf-8-sig"))
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

        if isinstance(data, dict):
            queries_list = data.get("queries", [])
        elif isinstance(data, list):
            queries_list = data
        else:
            raise ValueError("JSON must be an object with a 'queries' array or a plain array")

        if not isinstance(queries_list, list):
            raise ValueError("'queries' must be an array")

        result: list[ParsedQuery] = []
        for i, item in enumerate(queries_list):
            if not isinstance(item, dict):
                continue
            query_text = item.get("query_text", "").strip()
            pq = ParsedQuery(row=i + 1, query_text=query_text)

            for src in item.get("sources", []):
                if isinstance(src, dict):
                    doc_name = src.get("document_name", "").strip()
                    pages = src.get("pages", [])
                    if not isinstance(pages, list):
                        pages = []
                    pages = [p for p in pages if isinstance(p, (int, float))]
                    pages = [int(p) for p in pages]
                    if doc_name:
                        pq.sources.append(ParsedSource(document_name=doc_name, pages=pages))

            result.append(pq)

        return result

    @staticmethod
    def _parse_pages(pages_str: str) -> list[int]:
        """Parse a comma-separated page string like '1,2,5' into a list of ints."""
        pages: list[int] = []
        for part in pages_str.split(","):
            part = part.strip()
            if part.isdigit():
                pages.append(int(part))
        return pages

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    async def _build_document_lookup(self, project_id: UUID) -> dict[str, dict]:
        """Build a case-insensitive lookup of document names to {id, name} for a project."""
        result = await self.session.execute(
            select(Document.id, Document.title, Document.source_metadata)
            .where(Document.project_id == project_id)
        )
        lookup: dict[str, dict] = {}
        for row in result.all():
            doc_id, title, meta = row
            # Index by title (lowercase)
            display_name = title or "Unknown"
            lookup[display_name.lower()] = {"id": doc_id, "name": display_name}
            # Also index by filename from source_metadata
            if meta and isinstance(meta, dict):
                filename = meta.get("filename", "")
                if filename:
                    lookup[filename.lower()] = {"id": doc_id, "name": display_name}
        return lookup

    async def _get_existing_query_texts(self, golden_set_id: UUID) -> dict[str, str]:
        """Get existing query texts (lowercase) → query_id for duplicate detection."""
        result = await self.session.execute(
            select(GoldenSetQuery.id, func.lower(GoldenSetQuery.query_text))
            .where(GoldenSetQuery.golden_set_id == golden_set_id)
        )
        return {text: str(qid) for qid, text in result.all()}
