# PRD: Documents Feature

## Executive Summary

Add a Documents feature to RAG Admin, enabling users to upload, manage, and view PDF documents within projects. Documents are the foundational data source for RAG indexes—this feature provides the content that will be chunked, embedded, and indexed in subsequent features.

**Scope**: PDF upload, list, view, delete, metadata editing. Text extraction for RAG readiness. No chunking/indexing (that's the Index feature).

**Priority**: Simplicity and speed to unblock Index feature, with architecture designed for extensibility.

**Structure**: User → Project → Documents → Index (future)

---

## Change Log (MVP Simplifications)

**Last Updated**: 2025-02-04

This spec has been updated based on implementation planning discussions. Key changes from original:

### Schema Changes
- ✅ **Hybrid approach**: Universal fields as columns, source-specific in JSONB
- ✅ **Added** `source_type` and `source_identifier` columns for multi-source support
- ✅ **Removed** `quarantined` status (skipping ClamAV for MVP)
- ✅ **Changed** `extracted_text` from file path to TEXT column (DB storage)
- ✅ **Removed** separate `page_texts` storage (using `[Page N]` markers in extracted_text)
- ✅ **Added** `processing_metadata` JSONB field
- ✅ **Skipped** `team_id` future-proofing (YAGNI for MVP)

### Feature Simplifications
- ✅ **Viewer**: Text-only display + download (no react-pdf dual-panel) - Saves ~4-5 hours
- ✅ **ClamAV**: Skipped antivirus scanning for MVP - Saves ~2-3 hours
- ✅ **Text Storage**: Database TEXT column (not separate files) - Saves ~1 hour

### Rationale
All changes prioritize: **simplicity, time to MVP, and learning over production resilience**

**Time Saved**: ~8 hours (from 27 hours → 19 hours)
**Architecture Quality**: Preserved (Ports & Adapters, hybrid schema)
**Learning Value**: Preserved (async processing, JSONB, RAG patterns)

See `docs/planning/documents-feature-implementation-plan.md` for detailed implementation guide.

---

## Recommendations & Design Decisions

### 1. Multi-tenancy Approach (UPDATED: Skipped for MVP)

**Original Recommendation**: Add `team_id` (nullable) to Projects table for future-proofing.

**MVP Decision**: Skip `team_id` for now (YAGNI principle)

**Rationale**:
- ✅ Not on critical path for Documents feature
- ✅ Can add when actually building teams feature
- ✅ Avoids premature optimization
- ✅ Saves ~15 minutes

**Current Approach**:
- Documents belong to Projects (user-scoped)
- Documents inherit access through parent Project
- When teams feature is needed, add `team_id` then

---

### 2. Document Metadata for RAG + Agentic RAG

**Context**: Agentic RAG systems use document-level metadata to decide *which* documents to retrieve before chunking/searching. Richer metadata enables smarter agent routing.

**MVP Fields** (implement now):

| Field | Type | Purpose |
|-------|------|---------|
| `id` | UUID | Primary key |
| `project_id` | UUID FK | Parent project |
| `filename` | VARCHAR(255) | Original upload filename |
| `title` | VARCHAR(255) | User-editable display name (defaults to filename) |
| `description` | TEXT | User-provided summary (for agent context) |
| `file_path` | VARCHAR(500) | Storage location on disk |
| `file_size` | BIGINT | Size in bytes |
| `mime_type` | VARCHAR(100) | MIME type (application/pdf) |
| `checksum` | VARCHAR(64) | SHA-256 hash (deduplication, integrity) |
| `page_count` | INTEGER | Extracted from PDF |
| `status` | ENUM | processing, ready, failed, quarantined |
| `status_message` | TEXT | Error details if failed |
| `extracted_text_path` | VARCHAR(500) | Path to extracted text file |
| `created_by` | UUID FK | Uploading user |
| `created_at` | TIMESTAMPTZ | Upload timestamp |
| `updated_at` | TIMESTAMPTZ | Last modification |

**Future Extension Fields** (design for, don't implement):
- `source_url` - Original URL if scraped
- `document_type` - report, manual, article, etc.
- `language` - Detected or specified
- `custom_metadata` - JSONB for user-defined fields
- `version` - For document versioning

**Why These Fields Matter for Agentic RAG**:
- `title` + `description`: Agent can decide relevance without reading full content
- `page_count` + `file_size`: Agent can estimate processing cost
- `document_type`: Agent can filter by content category
- `checksum`: Prevents duplicate processing

---

### 3. File Size Policy

**Recommendation**: 25MB maximum per file

**Reasoning Framework**:

| Factor | Consideration | Impact |
|--------|--------------|--------|
| Infrastructure | 80GB VPS storage | 25MB × 1000 docs = 25GB, leaves headroom |
| UX Complexity | Under ~50MB, single-request uploads work | No chunked upload needed |
| Processing Time | Larger files = longer extraction | 25MB PDF extracts in <30 seconds |
| Typical Documents | Research papers: 1-10MB, Reports: 5-20MB | 25MB covers 95%+ of use cases |
| Budget Consideration | Smaller limit = less storage/bandwidth cost | Appropriate for learning project |

**Policy**: Simple, single number. No tiered limits or exceptions.

**Implementation**: Validate on frontend (immediate feedback) AND backend (security).

---

### 4. Storage Approach

**Recommendation**: Local filesystem for MVP

**Options Evaluated**:

| Option | Pros | Cons | Best For |
|--------|------|------|----------|
| **Local Filesystem** | Simplest, no extra services, fast reads | Not scalable, backup complexity | Single-server, MVP, learning |
| **Object Storage (S3/R2)** | Scalable, cheap, survives rebuilds | Additional service, latency, complexity | Production, multi-server |
| **Database BLOB** | Transactional, single backup | DB bloat, poor performance | Never for documents |

**Why Filesystem for Your Case**:
1. Single VPS deployment—no horizontal scaling needed
2. 80GB storage is plenty for a portfolio project
3. Simplest to implement and debug
4. Docker volumes make backups straightforward
5. Can migrate to S3-compatible later (design abstraction layer)

**Directory Structure**:
```
/data/
└── documents/
    └── {project_id}/
        └── {document_id}/
            ├── original.pdf          # Uploaded file
            └── extracted.txt         # Extracted text
```

**Design Pattern**: Create a `StorageService` abstraction so filesystem can be swapped for S3 later:

```python
class StorageService(Protocol):
    async def save(self, file: UploadFile, path: str) -> str: ...
    async def get(self, path: str) -> bytes: ...
    async def delete(self, path: str) -> None: ...
    def get_url(self, path: str) -> str: ...

class LocalStorageService(StorageService):
    # Filesystem implementation
    
# Future: class S3StorageService(StorageService): ...
```

**Docker Volume**: Mount `/data` as a Docker volume for persistence and easy backup.

---

### 5. Malware Protection (UPDATED: Skipping ClamAV for MVP)

**Original Recommendation**: Multi-layer validation with optional ClamAV scanning
**MVP Decision**: Skip ClamAV, use file validation only

**Layer 1: File Type Validation (Required - Sync)**

```python
ALLOWED_MIME_TYPES = {"application/pdf"}
PDF_MAGIC_BYTES = b"%PDF-"

def validate_file(file: UploadFile) -> None:
    # Check MIME type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise ValidationError("Only PDF files are allowed")
    
    # Check magic bytes (first 5 bytes)
    header = await file.read(5)
    await file.seek(0)
    if not header.startswith(PDF_MAGIC_BYTES):
        raise ValidationError("File is not a valid PDF")
    
    # Check file size
    if file.size > MAX_FILE_SIZE:
        raise ValidationError(f"File exceeds {MAX_FILE_SIZE_MB}MB limit")
```

**Layer 2: Secure Storage (Required)**
- Store outside webroot (files not directly URL-accessible)
- Serve through API endpoint with auth check
- Set `Content-Disposition: attachment` header (prevents browser execution)
- Sanitize filenames (remove path traversal attempts)

**Layer 3: ClamAV Scanning (SKIPPED FOR MVP)**

**MVP Decision**: Skip ClamAV for now

**Rationale**:
- ✅ Simpler setup (no Docker service, saves ~300MB RAM)
- ✅ Faster MVP (saves ~2-3 hours)
- ✅ Low risk (you control all uploads in learning environment)
- ✅ Layers 1 + 2 catch 95% of issues

**Future Enhancement**: Add ClamAV when:
- Moving to production with untrusted users
- Want to learn antivirus integration
- Need compliance with security policies

**If Adding Later**:
```yaml
# docker-compose.yml addition
clamav:
  image: clamav/clamav:latest
  volumes:
    - clamav-data:/var/lib/clamav
  healthcheck:
    test: ["CMD", "clamdscan", "--ping"]
  profiles:
    - security  # Only start with: docker compose --profile security up
```

---

### 6. Document Viewer Approach (UPDATED: Simplified for MVP)

**Original Recommendation**: Dual-panel with react-pdf + extracted text
**MVP Decision**: Text-only viewer + download button

**Rationale for Simplification**:
- ✅ Saves ~4-5 hours (no react-pdf integration)
- ✅ Focuses on RAG essentials (extracted text is what matters)
- ✅ Still supports core use cases (verification, debugging)
- ✅ Simpler dependencies (no PDF.js bundle)
- ✅ Download button for full PDF viewing in native apps

**MVP Implementation**:

```
┌─────────────────────────────────────────┐
│  Document: quarterly-report.pdf    [⬇️] │
├─────────────────────────────────────────┤
│  Extracted Text (Searchable)            │
│  ────────────────────────────────       │
│  [Full Text] [By Page]                  │
│                                         │
│  Page 1:                                │
│  Lorem ipsum dolor sit amet             │
│  consectetur adipiscing...              │
│                                         │
│  Page 2:                                │
│  Sed do eiusmod tempor...               │
│                                         │
├─────────────────────────────────────────┤
│  📄 12 pages  •  2.4 MB  •  5,234 words │
└─────────────────────────────────────────┘
```

**Components**:
1. **Text Display**: Shows extracted text with page markers
   - Two tabs: "Full Text" (combined) and "By Page" (page-by-page)
   - Searchable (browser Ctrl+F works)
   - Monospace font with good readability
   - Shows what the LLM "sees" for RAG debugging

2. **Download Button**: Opens original PDF in native viewer
   - For full visual inspection
   - Preserves original formatting

**Future Enhancement**: Add react-pdf dual-panel viewer when needed for:
- Visual PDF preview
- Page-level highlighting
- Annotation features

---

### 7. Transformations Visualization Location

**Recommendation**: Transformations belong in the **Index feature**, NOT Documents

**Reasoning**:

| Factor | Documents Feature | Index Feature |
|--------|------------------|---------------|
| Chunking config lives where? | ❌ No config here | ✅ Per-index settings |
| Same doc, different indexes? | Doc is static | ✅ Different chunk strategies |
| User mental model | "Here's my content" | "How should I process it?" |
| Preview timing | Before any config exists | ✅ After config, before commit |

**Documents Feature Shows**:
- Original PDF render
- Extracted raw text (what we got from PDF)
- Basic stats: page count, word count, character count

**Index Feature Shows** (future):
- Chunk preview with current settings
- Chunk boundaries overlaid on document
- Token counts per chunk
- Overlap visualization

**Why This Matters**: A user might chunk the same document differently for:
- "Quick answers" index: Small chunks (256 tokens)
- "Deep analysis" index: Large chunks (1024 tokens)

Showing chunks at document level would be confusing—which config's chunks?

---

### 8. MVP Scope

**Goal**: Minimum to unblock Index feature development

**What Index Feature Needs from Documents**:
1. ✅ Documents exist and can be selected
2. ✅ Document files are accessible for processing
3. ✅ Extracted text available (or extractable)
4. ✅ Basic metadata for retrieval context

**MVP Includes**:

| Feature | Priority | Notes |
|---------|----------|-------|
| Upload single PDF | P0 | With drag-drop (shadcn pattern) |
| List documents in project | P0 | Table with name, size, date, status |
| View document | P0 | PDF preview + extracted text |
| Delete document | P0 | Block if in any index |
| Edit metadata | P1 | Title and description only |
| File validation | P0 | MIME type + magic bytes |
| Async processing | P0 | FastAPI BackgroundTasks |
| ClamAV scanning | P1 | Async, adds security depth |

**MVP Excludes** (future iterations):

| Feature | Reason to Defer |
|---------|-----------------|
| Batch upload | Single file covers MVP needs |
| Folder organization | "Start minimal" per your input |
| Versioning | Complexity, not needed for Index |
| Soft delete / trash | Simple delete-if-not-indexed is cleaner |
| Other file types | "Start with PDF, extend later" |
| Chunk visualization | Belongs in Index feature |

---

### 10. RAG Framework Abstraction (Ports & Adapters)

**Goal**: Use LlamaIndex for MVP speed, enable migration to LangChain for marketability, avoid framework lock-in

**Strategy**:
- **MVP**: LlamaIndex (your current familiarity → faster development)
- **Future**: LangChain adapter (more marketable, broader ecosystem)
- **Architecture**: Ports & Adapters pattern enables swap without service changes

**Pattern**: Hexagonal Architecture (Ports & Adapters)

```
┌─────────────────────────────────────────────────────────────┐
│                     Your Application                         │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Domain / Business Logic                 │    │
│  │                                                      │    │
│  │   DocumentService    ChunkingService    IndexService │    │
│  │         │                  │                  │      │    │
│  └─────────┼──────────────────┼──────────────────┼──────┘    │
│            │                  │                  │           │
│      ┌─────▼─────┐      ┌─────▼─────┐      ┌─────▼─────┐     │
│      │   Port    │      │   Port    │      │   Port    │     │
│      │ (Protocol)│      │ (Protocol)│      │ (Protocol)│     │
│      └─────┬─────┘      └─────┬─────┘      └─────┬─────┘     │
└────────────┼────────────────────┼──────────────────┼─────────┘
             │                    │                  │
       ┌─────▼─────┐        ┌─────▼─────┐      ┌─────▼─────┐
       │  Adapter  │        │  Adapter  │      │  Adapter  │
       │LlamaIndex │        │LlamaIndex │      │LlamaIndex │
       │  (MVP)    │        │  (MVP)    │      │  (MVP)    │
       └───────────┘        └───────────┘      └───────────┘
             │                    │                  │
       ┌─────▼─────┐        ┌─────▼─────┐      ┌─────▼─────┐
       │  Adapter  │        │  Adapter  │      │  Adapter  │
       │ LangChain │        │ LangChain │      │ LangChain │
       │ (Future)  │        │ (Future)  │      │ (Future)  │
       └───────────┘        └───────────┘      └───────────┘
```

**Core Interfaces (Ports)**:

```python
# app/ports/document_processing.py
from typing import Protocol
from dataclasses import dataclass

@dataclass
class TextChunk:
    """Framework-agnostic chunk representation."""
    content: str
    index: int
    start_char: int
    end_char: int
    token_count: int | None = None
    metadata: dict = None

@dataclass  
class ExtractedDocument:
    """Framework-agnostic extraction result."""
    text: str
    pages: list[str]
    page_count: int
    metadata: dict

class DocumentExtractor(Protocol):
    """Port: Extract text from documents."""
    async def extract(self, file_path: str, mime_type: str) -> ExtractedDocument: ...
    def supported_types(self) -> list[str]: ...

class TextSplitter(Protocol):
    """Port: Split text into chunks."""
    def split(
        self, 
        text: str, 
        chunk_size: int, 
        chunk_overlap: int,
        strategy: str = "recursive"
    ) -> list[TextChunk]: ...
    
    def supported_strategies(self) -> list[str]: ...

class EmbeddingGenerator(Protocol):
    """Port: Generate embeddings from text."""
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_single(self, text: str) -> list[float]: ...
    def dimension(self) -> int: ...
```

**LlamaIndex Adapter (MVP)**:

```python
# app/adapters/llamaindex/extractor.py
from app.ports.document_processing import DocumentExtractor, ExtractedDocument

class LlamaIndexExtractor:
    """Adapter: LlamaIndex implementation of DocumentExtractor port."""
    
    async def extract(self, file_path: str, mime_type: str) -> ExtractedDocument:
        from llama_index.core import SimpleDirectoryReader
        
        if mime_type != "application/pdf":
            raise ValueError(f"Unsupported: {mime_type}")
        
        # LlamaIndex extraction
        reader = SimpleDirectoryReader(input_files=[file_path])
        documents = reader.load_data()
        
        # Convert to our framework-agnostic model
        pages = [doc.text for doc in documents]
        
        return ExtractedDocument(
            text="\n\n".join(pages),
            pages=pages,
            page_count=len(pages),
            metadata=documents[0].metadata if documents else {},
        )
    
    def supported_types(self) -> list[str]:
        return ["application/pdf"]
```

**Future LangChain Adapter**:

```python
# app/adapters/langchain/extractor.py (future implementation)
from app.ports.document_processing import DocumentExtractor, ExtractedDocument

class LangChainExtractor:
    """Adapter: LangChain implementation of DocumentExtractor port."""
    
    async def extract(self, file_path: str, mime_type: str) -> ExtractedDocument:
        from langchain_community.document_loaders import PyPDFLoader
        
        if mime_type != "application/pdf":
            raise ValueError(f"Unsupported: {mime_type}")
        
        loader = PyPDFLoader(file_path)
        pages = loader.load()
        
        return ExtractedDocument(
            text="\n\n".join(p.page_content for p in pages),
            pages=[p.page_content for p in pages],
            page_count=len(pages),
            metadata=pages[0].metadata if pages else {},
        )
    
    def supported_types(self) -> list[str]:
        return ["application/pdf"]
```

**Dependency Injection**:

```python
# app/core/dependencies.py
from functools import lru_cache
from app.core.config import settings
from app.ports.document_processing import DocumentExtractor

@lru_cache
def get_document_extractor() -> DocumentExtractor:
    """Factory: swap implementations via config."""
    if settings.RAG_FRAMEWORK == "llamaindex":
        from app.adapters.llamaindex.extractor import LlamaIndexExtractor
        return LlamaIndexExtractor()
    elif settings.RAG_FRAMEWORK == "langchain":
        from app.adapters.langchain.extractor import LangChainExtractor
        return LangChainExtractor()
    raise ValueError(f"Unknown RAG framework: {settings.RAG_FRAMEWORK}")
```

**Benefits**:

| Benefit | How It Helps |
|---------|--------------|
| **Speed to MVP** | LlamaIndex familiarity → faster development |
| **Marketability** | Add LangChain adapter for portfolio/job relevance |
| **Test isolation** | Mock the Protocol, test business logic without frameworks |
| **Framework comparison** | Blog post: "LlamaIndex vs LangChain: A Practical Comparison" |
| **Future-proof** | New framework = new adapter, no service changes |

**Directory Structure**:

```
backend/app/
├── ports/                    # Your interfaces (Protocols)
│   ├── __init__.py
│   ├── document_processing.py  # Extractor, Splitter, Embedder
│   └── vector_store.py
├── adapters/                 # Framework implementations
│   ├── llamaindex/          # MVP implementation
│   │   ├── __init__.py
│   │   ├── extractor.py
│   │   ├── splitter.py      # Future: Index feature
│   │   └── embeddings.py    # Future: Index feature
│   └── langchain/           # Future migration
│       └── ...
├── services/                 # Business logic (depends on ports only)
│   ├── document_service.py
│   ├── chunking_service.py
│   └── indexing_service.py
└── core/
    └── dependencies.py       # DI configuration
```

**Implementation Note**: For Documents feature MVP, only `DocumentExtractor` port is needed. `TextSplitter` and `EmbeddingGenerator` come with the Index feature.

---

### 9. Background Jobs

**Recommendation**: Use FastAPI BackgroundTasks for MVP, graduate to task queue when needed

**Understanding Python Async Options**:

| Approach | How It Works | Persistence | Retries | Survives Crash |
|----------|--------------|-------------|---------|----------------|
| **FastAPI BackgroundTasks** | Same process, after response | ❌ Memory | ❌ Manual | ❌ Lost |
| **asyncio.create_task()** | Same process, fire-and-forget | ❌ Memory | ❌ Manual | ❌ Lost |
| **Task Queue (ARQ/Celery)** | Separate worker + Redis | ✅ Redis | ✅ Built-in | ✅ Re-queued |

**Why BackgroundTasks for MVP**:

| Factor | Benefit |
|--------|---------|
| Zero dependencies | No Redis, no worker process |
| Deep async learning | Understand native Python patterns first |
| Feel the pain | Experience limitations → informed decision to add queue |
| Faster MVP | Less infrastructure to set up |

**When to Graduate to Task Queue**:
- Server restarts leave documents stuck in "processing" → Need persistence
- Processing blocks other requests → Need separate worker
- Want retry with backoff → Need queue features
- This becomes a great learning story for portfolio/blog

**Implementation Approach**:

```python
from fastapi import BackgroundTasks

@router.post("/documents", status_code=202)
async def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    # Sync validation (fast, blocks)
    validate_file(file)
    
    # Save to temp, create DB record
    temp_path = await save_temp_file(file)
    document = await create_document_record(db, status="processing")
    
    # Schedule background work - returns IMMEDIATELY after this
    background_tasks.add_task(
        process_document,
        document_id=document.id,
        temp_path=temp_path,
    )
    
    return DocumentResponse(id=document.id, status="processing")


async def process_document(document_id: UUID, temp_path: str):
    """Runs after response is sent, in same process."""
    async with get_db_session() as db:
        try:
            # Move file, extract text (slow operations)
            final_path = await move_to_permanent_storage(temp_path)
            extracted = await extractor.extract(final_path, "application/pdf")
            
            # Update DB
            await update_document(db, document_id, 
                status="ready",
                file_path=final_path,
                page_count=extracted.page_count,
            )
        except Exception as e:
            await update_document(db, document_id,
                status="failed",
                status_message=str(e),
            )
```

**Key Insight**: `asyncio` makes code *non-blocking* (other requests can be handled), but the HTTP connection waits unless you use BackgroundTasks. BackgroundTasks runs *after* the response is sent.

**Status Polling**: Frontend polls `GET /documents/{id}` every 2-3 seconds while status is `processing`. Consider WebSocket for real-time updates in future iteration.

**Future Migration Path**: When you feel the pain (stuck documents after restart, need retries), introduce ARQ + Redis. Document this journey for your portfolio.

---

## Database Schema

### Documents Table (UPDATED: Hybrid Approach)

**Key Changes from Original Spec**:
- ✅ Hybrid schema: universal fields as columns, source-specific in JSONB
- ✅ Removed `quarantined` status (skipping ClamAV for MVP)
- ✅ Added `source_type` and `source_identifier` for multi-source support
- ✅ Changed `extracted_text` from file path to TEXT column (stored in DB)
- ✅ Removed separate `page_texts` storage (using `[Page N]` markers in extracted_text)
- ✅ Added `processing_metadata` JSONB for extraction info

```sql
CREATE TYPE document_status AS ENUM ('processing', 'ready', 'failed');

CREATE TABLE documents (
    -- Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    -- Source tracking (supports multi-source future)
    source_type VARCHAR(50) NOT NULL,        -- 'upload', 'gdrive', 'web', 'notion', 'github'
    source_identifier VARCHAR(500) NOT NULL, -- Checksum for uploads, URL for web, etc.

    -- Universal metadata
    title VARCHAR(255) NOT NULL,
    description TEXT,

    -- Content (for RAG - stored in DB for MVP)
    extracted_text TEXT,  -- Full text with [Page N] markers embedded

    -- Source-specific details (JSONB for flexibility)
    source_metadata JSONB NOT NULL DEFAULT '{}',
    -- For upload: {filename, file_path, file_size, mime_type, checksum, page_count}
    -- For web: {url, domain, scraped_at, word_count}
    -- For notion: {page_id, workspace_id, last_edited_time}

    -- Processing metadata (JSONB for extraction info)
    processing_metadata JSONB DEFAULT '{}',
    -- {extraction_method, extraction_version, extracted_at, duration_ms, token_count}

    -- Status tracking
    status document_status NOT NULL DEFAULT 'processing',
    status_message TEXT,

    -- Audit
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints (prevents duplicate content per source type)
    CONSTRAINT uq_documents_project_source
    UNIQUE (project_id, source_type, source_identifier)
);

-- Indexes
CREATE INDEX ix_documents_project_id ON documents(project_id);
CREATE INDEX ix_documents_source_type ON documents(source_type);
CREATE INDEX ix_documents_status ON documents(status);
CREATE INDEX ix_documents_created_at ON documents(created_at);

-- GIN indexes for JSONB querying
CREATE INDEX ix_documents_source_metadata ON documents USING GIN (source_metadata);
CREATE INDEX ix_documents_processing_metadata ON documents USING GIN (processing_metadata);
```

**Index Rationale**:
- `ix_documents_project_id`: List documents in project
- `ix_documents_source_type`: Filter by source (upload, web, etc.)
- `ix_documents_status`: Filter by processing state
- `ix_documents_created_at`: Sort by upload date
- `ix_documents_source_metadata`: JSONB queries (e.g., filter by checksum, URL)
- `ix_documents_processing_metadata`: JSONB queries (e.g., extraction method)
- `uq_documents_project_source`: Prevent duplicates per source type

**Example Data for Upload**:
```json
{
  "source_type": "upload",
  "source_identifier": "sha256_checksum_abc123...",
  "title": "Quarterly Report",
  "extracted_text": "[Page 1]\nIntroduction text...\n\n[Page 2]\nBackground...",
  "source_metadata": {
    "filename": "quarterly-report.pdf",
    "file_path": "project_id/doc_id/original.pdf",
    "file_size": 2456789,
    "mime_type": "application/pdf",
    "checksum": "sha256_checksum_abc123...",
    "page_count": 12
  },
  "processing_metadata": {
    "extraction_method": "llamaindex",
    "extraction_version": "0.9.48",
    "extracted_at": "2025-01-15T10:30:00Z",
    "extraction_duration_ms": 1234,
    "token_count": 5000,
    "character_count": 45678
  }
}

### Future: Index-Document Relationship

When Index feature is built:
```sql
CREATE TABLE index_documents (
    index_id     UUID NOT NULL REFERENCES indexes(id) ON DELETE CASCADE,
    document_id  UUID NOT NULL REFERENCES documents(id) ON DELETE RESTRICT,
    added_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (index_id, document_id)
);
```

The `ON DELETE RESTRICT` enforces: cannot delete document if it's in any index.

---

## API Specification

### Base URL
`/api/v1/projects/{project_id}/documents`

### Authentication
All endpoints require valid JWT access token

### Endpoints

| Method | Endpoint | Description | Request | Response | Status |
|--------|----------|-------------|---------|----------|--------|
| POST | `/documents` | Upload document | Multipart form | `DocumentResponse` | 202 |
| GET | `/documents` | List documents | Query params | `DocumentResponse[]` | 200 |
| GET | `/documents/{id}` | Get document metadata | - | `DocumentResponse` | 200 |
| GET | `/documents/{id}/file` | Download original file | - | Binary (PDF) | 200 |
| GET | `/documents/{id}/text` | Get extracted text | - | `ExtractedTextResponse` | 200 |
| PATCH | `/documents/{id}` | Update metadata | `DocumentUpdate` | `DocumentResponse` | 200 |
| DELETE | `/documents/{id}` | Delete document | - | - | 204 |

**Note**: Upload returns 202 Accepted (not 201 Created) because processing happens asynchronously. The document exists but may still be in `processing` status.

### Request/Response Schemas

**Upload (Multipart Form)**:
```
POST /api/v1/projects/{project_id}/documents
Content-Type: multipart/form-data

file: <binary PDF>
title: "Quarterly Report Q4 2024" (optional, defaults to filename)
description: "Financial results and projections" (optional)
```

**DocumentResponse**:
```json
{
  "id": "uuid",
  "projectId": "uuid",
  "filename": "quarterly-report.pdf",
  "title": "Quarterly Report Q4 2024",
  "description": "Financial results and projections",
  "fileSize": 2456789,
  "mimeType": "application/pdf",
  "pageCount": 12,
  "status": "ready",
  "statusMessage": null,
  "createdBy": "uuid",
  "createdAt": "2025-01-15T10:30:00Z",
  "updatedAt": "2025-01-15T10:30:00Z"
}
```

**DocumentUpdate** (all fields optional):
```json
{
  "title": "string (max 255 chars)",
  "description": "string"
}
```

**ExtractedTextResponse**:
```json
{
  "documentId": "uuid",
  "pageCount": 12,
  "totalCharacters": 45678,
  "totalWords": 8234,
  "pages": [
    {
      "pageNumber": 1,
      "text": "Page content here..."
    }
  ]
}
```

**List Query Parameters**:
- `status`: Filter by status (processing, ready, failed, quarantined)
- `sort`: Sort field (created_at, filename, file_size) - default: created_at
- `order`: Sort order (asc, desc) - default: desc

### Error Responses

| Status | Condition |
|--------|-----------|
| 400 Bad Request | Invalid file type, file too large, validation error |
| 401 Unauthorized | Missing or invalid auth token |
| 404 Not Found | Document or project not found, or doesn't belong to user |
| 409 Conflict | Duplicate file (same checksum) in project |
| 422 Unprocessable Entity | Invalid request data |

---

## Architecture

### Backend Layer Structure

```
Upload Request
    ↓
Router (app/routers/documents.py)
    ├── Validate file type/size (sync, fast)
    ├── Save to temp location (sync, fast)
    ├── Create DB record: status='processing'
    ├── Schedule BackgroundTask
    └── Return 202 Accepted immediately
    
BackgroundTask (same process, after response)
    ├── Move file to permanent storage
    ├── DocumentExtractor.extract() → Text (via LlamaIndex adapter)
    ├── (Optional) ClamAV scan
    ├── Update DB: status='ready' or 'failed'
    └── Cleanup temp file
```

**Ports & Adapters Structure**:

```
┌─────────────────────────────────────────────────────┐
│                   Services Layer                     │
│  DocumentService (depends on Ports, not LlamaIndex) │
└─────────────────────────┬───────────────────────────┘
                          │
              ┌───────────▼───────────┐
              │    Ports (Protocols)   │
              │  DocumentExtractor     │
              │  StorageService        │
              └───────────┬───────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
┌───────▼───────┐ ┌───────▼───────┐ ┌───────▼───────┐
│   Adapters    │ │   Adapters    │ │   Adapters    │
│  LlamaIndex   │ │ LocalStorage  │ │  (Future)     │
│  Extractor    │ │               │ │  S3Storage    │
└───────────────┘ └───────────────┘ └───────────────┘
```

**Key Files**:

```
backend/
├── app/
│   ├── models/
│   │   └── document.py              # SQLAlchemy model
│   ├── schemas/
│   │   └── document.py              # Pydantic schemas
│   ├── ports/                       # Interfaces (Protocols)
│   │   ├── __init__.py
│   │   ├── document_processing.py   # DocumentExtractor protocol
│   │   └── storage.py               # StorageService protocol
│   ├── adapters/                    # Implementations
│   │   ├── llamaindex/              # MVP implementation
│   │   │   ├── __init__.py
│   │   │   └── extractor.py         # LlamaIndex PDF extractor
│   │   └── storage/
│   │       └── local.py             # Local filesystem storage
│   ├── repositories/
│   │   └── document_repository.py   # Database operations
│   ├── services/
│   │   └── document_service.py      # Business logic + background processing
│   ├── routers/
│   │   └── documents.py             # API endpoints
│   └── core/
│       ├── config.py                # Settings
│       └── dependencies.py          # DI factories
├── alembic/versions/
│   └── XXXXX_add_documents_table.py
└── tests/
    ├── repositories/
    │   └── test_document_repository.py
    ├── services/
    │   └── test_document_service.py
    ├── adapters/
    │   └── test_llamaindex_extractor.py
    └── routers/
        └── test_documents.py
```

### Frontend Architecture

```
API Client (axios)
    ↓
Custom Hook (useDocuments)
    ↓
Page Component (ProjectDocumentsPage)
    ↓
    ├── DocumentUploadZone (drag-drop upload)
    ├── DocumentsTable (list view)
    ├── DocumentViewDialog (PDF + text viewer)
    ├── DocumentEditDialog (metadata form)
    └── DocumentDeleteConfirmDialog
```

**Key Files**:

```
frontend/src/
├── types/
│   └── document.ts                  # TypeScript interfaces
├── api/
│   └── documents.ts                 # API client
├── hooks/
│   └── useDocuments.ts              # State management
├── pages/
│   └── ProjectDocumentsPage.tsx     # Main page
└── components/documents/
    ├── DocumentUploadZone.tsx       # Drag-drop upload
    ├── DocumentsTable.tsx           # Document list
    ├── DocumentViewDialog.tsx       # PDF viewer + text
    ├── DocumentEditDialog.tsx       # Edit metadata
    └── DocumentStatusBadge.tsx      # Status indicator
```

---

## Design Decisions & Trade-offs

### 1. Filesystem vs Object Storage

**Decision**: Local filesystem with abstraction layer

**Trade-off**:
| Factor | Filesystem | Object Storage |
|--------|-----------|----------------|
| Simplicity | ✅ Simple | ❌ Extra service |
| Cost | ✅ Included in VPS | ❌ Additional cost |
| Scalability | ❌ Single server | ✅ Unlimited |
| Durability | ⚠️ Server-dependent | ✅ Replicated |

**Mitigation**: `StorageService` protocol allows future migration to S3-compatible storage.

### 2. Native Async with BackgroundTasks

**Decision**: Use FastAPI BackgroundTasks for MVP, graduate to task queue when needed

**Trade-off**:
| Factor | BackgroundTasks | Task Queue (ARQ) |
|--------|----------------|------------------|
| Dependencies | ✅ None (native) | ❌ Redis + worker |
| Persistence | ❌ Memory only | ✅ Redis |
| Crash recovery | ❌ Tasks lost | ✅ Re-queued |
| Learning value | ✅ Deep async understanding | ⚠️ Framework abstraction |
| MVP speed | ✅ Fast | ❌ More setup |

**Rationale**: Feel the limitations firsthand → informed decision to add queue later. Great learning journey for portfolio.

### 3. Ports & Adapters for RAG Frameworks

**Decision**: Define own interfaces, start with LlamaIndex, migrate to LangChain later

**Trade-off**:
| Factor | Direct Framework Use | Ports & Adapters |
|--------|---------------------|------------------|
| Initial velocity | ✅ Faster start | ❌ More scaffolding |
| Framework lock-in | ❌ Coupled | ✅ Swappable |
| Testing | ❌ Mock framework internals | ✅ Mock at port boundary |
| Migration path | ❌ Rewrite | ✅ New adapter only |

**Why LlamaIndex First**:
- Your current familiarity → faster MVP
- Simpler API for document loading
- Add LangChain adapter later for marketability

**Rationale**: Portfolio project should demonstrate architecture sophistication. Pattern enables framework comparison for future content/blog posts.

### 4. ClamAV vs No Scanning

**Decision**: Include ClamAV (recommended)

**Trade-off**:
| Factor | With ClamAV | Without |
|--------|------------|---------|
| Security | ✅ Standard practice | ⚠️ Trust-based |
| Resources | ❌ ~300MB RAM | ✅ Nothing |
| Complexity | ⚠️ Docker service | ✅ Simple |
| Portfolio | ✅ Demonstrates security | ❌ Gap |

**If Skipping ClamAV**: Document as "Future: Add antivirus scanning" in README.

### 5. Viewer: react-pdf vs react-doc-viewer

**Decision**: Start with react-pdf, design abstraction for future formats

**Trade-off**:
| Factor | react-pdf | react-doc-viewer |
|--------|-----------|------------------|
| PDF quality | ✅ Excellent | ⚠️ Good |
| Multi-format | ❌ PDF only | ✅ Many formats |
| Privacy | ✅ Local rendering | ❌ External services for Office |
| Future work | ⚠️ Add viewers later | ✅ Already supported |

**Rationale**: Privacy concern with react-doc-viewer sending docs to Google/Microsoft. PDFs are primary RAG format. Server-side extraction handles other formats for RAG anyway.

### 6. Delete Behavior: Block vs Cascade

**Decision**: Block deletion if document in any index

**Trade-off**:
| Factor | Block | Cascade |
|--------|-------|---------|
| Data safety | ✅ Prevents accidents | ❌ Silent data loss |
| UX clarity | ✅ Explicit error | ⚠️ Hidden side effects |
| Simplicity | ✅ Simple rule | ❌ Complex cleanup |

**Implementation**: Query `index_documents` table; if count > 0, return 400 error.

---

## Implementation Phases

### Phase 1: Database & Models (Backend)

**Steps**:
1. Create Alembic migration for `documents` table
2. Create `DocumentStatus` enum
3. Create `Document` SQLAlchemy model
4. Create Pydantic schemas (`DocumentCreate`, `DocumentUpdate`, `DocumentResponse`)

**Verification**:
```bash
alembic upgrade head
# Check table exists with correct columns and indexes
```

### Phase 2: Ports & Adapters Foundation (Backend)

**Steps**:
1. Create `app/ports/storage.py` - StorageService protocol
2. Create `app/ports/document_processing.py` - DocumentExtractor protocol
3. Create `app/adapters/storage/local.py` - LocalStorageService
4. Create `app/adapters/llamaindex/extractor.py` - LlamaIndex PDF extractor
5. Create `app/core/dependencies.py` - DI factory functions
6. Add file validation utilities

**Verification**:
```python
# Manual test
from app.adapters.storage.local import LocalStorageService
from app.adapters.llamaindex.extractor import LlamaIndexExtractor

storage = LocalStorageService("/data/documents")
path = await storage.save(file_bytes, "test/doc.pdf")
content = await storage.get(path)

extractor = LlamaIndexExtractor()
result = await extractor.extract(path, "application/pdf")
assert result.page_count > 0
```

### Phase 3: Repository & Service Layers (Backend)

**Steps**:
1. Create `DocumentRepository` with CRUD operations
2. Create `DocumentService` with business logic:
   - Upload initiation (validate → save temp → create record → schedule BackgroundTask)
   - Background processing function (move file, extract, update status)
   - Status checking
   - Delete validation (check index membership)
   - Duplicate detection (checksum)
3. Add custom exceptions (`DuplicateDocumentError`, `DocumentInUseError`)

**Verification**:
- Repository unit tests
- Service unit tests with mocked dependencies

### Phase 4: API Endpoints (Backend)

**Steps**:
1. Create `documents.py` router
2. Implement upload endpoint (returns 202 Accepted)
3. Implement status/list/get endpoints
4. Implement file download endpoint
5. Implement text retrieval endpoint
6. Add to main FastAPI app
7. Configure multipart upload handling

**Verification**:
```bash
# Upload (returns immediately with processing status)
curl -X POST http://localhost:8000/api/v1/projects/{id}/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.pdf" \
  -F "title=Test Document"
# Response: 202 Accepted, {"id": "...", "status": "processing"}

# Poll status
curl http://localhost:8000/api/v1/projects/{id}/documents/{doc_id} \
  -H "Authorization: Bearer $TOKEN"
# Response: {"status": "ready", ...} or {"status": "processing", ...}

# Download after ready
curl http://localhost:8000/api/v1/projects/{id}/documents/{doc_id}/file \
  -H "Authorization: Bearer $TOKEN" \
  -o downloaded.pdf
```

### Phase 5: Frontend API Layer

**Steps**:
1. Create `frontend/src/types/document.ts`
2. Create `frontend/src/api/documents.ts` with:
   - Upload with progress
   - Status polling helper
3. Create `frontend/src/hooks/useDocuments.ts` with:
   - Auto-polling for processing documents
   - Optimistic updates

**Verification**:
- Test API calls in browser console
- Verify upload progress events fire
- Verify polling stops when document is ready

### Phase 6: Frontend UI Components

**Steps**:
1. Create `DocumentUploadZone.tsx` (drag-drop with progress)
2. Create `DocumentsTable.tsx` (list with status indicators)
3. Create `DocumentStatusBadge.tsx` (animated processing state)
4. Create `DocumentEditDialog.tsx` (metadata form)
5. Create `DocumentDeleteConfirmDialog.tsx`

**Verification**:
- Components render in isolation
- Styling matches existing patterns
- Processing animation visible

### Phase 7: Document Viewer

**Steps**:
1. Install `react-pdf` package
2. Create `DocumentViewer.tsx` - abstraction component
3. Create `PDFViewer.tsx` - react-pdf implementation:
   - PDF preview panel (left)
   - Extracted text panel (right)
   - Download button
   - Page navigation
4. Style with Tailwind/Shadcn patterns

**Verification**:
- PDF renders correctly
- Text panel shows extracted content
- Navigation works
- Responsive layout

### Phase 8: Integration & Testing

**Steps**:
1. Create `ProjectDocumentsPage.tsx` (wire components)
2. Add route to React Router
3. Integration tests for full workflows
4. Manual E2E testing
5. Add adapter tests for LlamaIndex extractor

**Verification**:
- Full checklist below

---

## Testing Strategy

### Backend Tests

**Repository Tests** (`tests/repositories/test_document_repository.py`):
- Create document
- Get by ID (found/not found)
- Get scoped to project (security: wrong project returns None)
- List documents (with status filter)
- Get by checksum (duplicate detection)
- Update document
- Delete document

**Service Tests** (`tests/services/test_document_service.py`):
- Upload valid PDF → success
- Upload invalid file type → ValidationError
- Upload oversized file → ValidationError  
- Upload duplicate (same checksum) → ConflictError
- Delete document not in index → success
- Delete document in index → DocumentInUseError
- Update metadata → success
- Get extracted text → success

**Router Tests** (`tests/routers/test_documents.py`):
- `POST /documents` (valid) → 202 Accepted
- `POST /documents` (invalid type) → 400
- `POST /documents` (too large) → 400
- `POST /documents` (duplicate) → 409
- `POST /documents` (unauthenticated) → 401
- `GET /documents` → 200 with list
- `GET /documents?status=ready` → filtered list
- `GET /documents/{id}` → 200
- `GET /documents/{id}` (not found) → 404
- `GET /documents/{id}/file` → 200 with PDF
- `GET /documents/{id}/file` (still processing) → 409 or 202
- `GET /documents/{id}/text` → 200 with extracted text
- `GET /documents/{id}/text` (still processing) → 409 or 202
- `PATCH /documents/{id}` → 200
- `DELETE /documents/{id}` → 204
- `DELETE /documents/{id}` (in index) → 400

### Frontend Tests (Optional for MVP)

- Component rendering (upload zone, table, viewer)
- Hook state transitions
- Upload progress handling

---

## Verification Checklist

### Backend Verification

- [ ] Database migration runs without errors
- [ ] Indexes created correctly
- [ ] Unique constraint on (project_id, checksum) works
- [ ] Storage directory created and writable
- [ ] All repository tests pass
- [ ] All service tests pass
- [ ] All router tests pass
- [ ] Manual API testing:
  - [ ] Upload PDF successfully
  - [ ] Duplicate upload returns 409
  - [ ] Invalid file type returns 400
  - [ ] Oversized file returns 400
  - [ ] List documents returns correct data
  - [ ] Download file returns valid PDF
  - [ ] Get extracted text returns content
  - [ ] Update metadata works
  - [ ] Delete works (when not in index)

### Frontend Verification

- [ ] Documents page loads without errors
- [ ] Upload zone accepts drag-drop
- [ ] Upload progress indicator works
- [ ] Documents table displays all fields
- [ ] Status badge shows correct state
- [ ] View dialog opens PDF correctly
- [ ] Extracted text displays alongside PDF
- [ ] Page navigation works
- [ ] Download button works
- [ ] Edit dialog pre-fills data
- [ ] Delete confirmation works
- [ ] Error messages display correctly

### End-to-End Workflow

1. Sign in to application
2. Navigate to a project
3. Go to Documents tab
4. Drag PDF onto upload zone
5. Verify progress indicator
6. Verify document appears in list with "processing" then "ready"
7. Click document to open viewer
8. Verify PDF renders
9. Verify extracted text shows
10. Navigate pages in PDF
11. Download file, verify it opens locally
12. Edit document title/description
13. Verify changes reflected in list
14. Try to delete (should succeed if not indexed)
15. Upload same file again (should fail - duplicate)
16. Upload non-PDF file (should fail - invalid type)

---

## Security Considerations

### File Upload Security

| Threat | Mitigation |
|--------|------------|
| Malicious file type | MIME check + magic bytes validation |
| Path traversal | Sanitize filename, use UUID paths |
| Malware | ClamAV scanning (optional) |
| XSS via filename | Escape display, Content-Disposition |
| Unauthorized access | Auth check on all endpoints |
| Directory listing | Files stored by UUID, not enumerable |

### Implementation Notes

```python
# Filename sanitization
import re
from pathlib import Path

def sanitize_filename(filename: str) -> str:
    # Remove path components
    name = Path(filename).name
    # Remove dangerous characters
    name = re.sub(r'[^\w\-_\.]', '_', name)
    # Limit length
    return name[:255]

# Secure file serving
@router.get("/{document_id}/file")
async def download_file(...):
    # ... auth checks ...
    return FileResponse(
        path=document.file_path,
        filename=document.filename,
        media_type=document.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{document.filename}"'
        }
    )
```

---

## Docker Configuration

### Services for Document Processing

```yaml
# docker-compose.yml
services:
  backend:
    build: ./backend
    volumes:
      - documents-data:/data/documents
    environment:
      - DOCUMENT_STORAGE_PATH=/data/documents
      - MAX_UPLOAD_SIZE_MB=25
      - RAG_FRAMEWORK=llamaindex
    depends_on:
      - db

  # Optional: ClamAV for malware scanning
  clamav:
    image: clamav/clamav:latest
    volumes:
      - clamav-data:/var/lib/clamav
    healthcheck:
      test: ["CMD", "clamdscan", "--ping"]
      interval: 60s
      timeout: 10s
      retries: 3
    profiles:
      - security  # Only start with: docker compose --profile security up

volumes:
  documents-data:
  clamav-data:
```

### Environment Variables

```env
# .env
DOCUMENT_STORAGE_PATH=/data/documents
MAX_UPLOAD_SIZE_MB=25
ALLOWED_MIME_TYPES=application/pdf

# RAG framework selection
RAG_FRAMEWORK=llamaindex  # MVP: llamaindex, Future: langchain

# Optional: ClamAV
CLAMAV_ENABLED=false
CLAMAV_HOST=clamav
CLAMAV_PORT=3310
```

### Future: Task Queue (When Needed)

When you experience limitations with BackgroundTasks (stuck processing after restart, need retries), add:

```yaml
# docker-compose.yml additions for task queue
services:
  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      
  worker:
    build: ./backend
    command: arq app.worker.WorkerSettings
    depends_on:
      - redis
      - db
    volumes:
      - documents-data:/data/documents
    environment:
      - REDIS_URL=redis://redis:6379
      - RAG_FRAMEWORK=llamaindex

volumes:
  redis-data:
```

---

## Future Enhancements (Out of Scope)

### Immediate Next (Index Feature)
- Select documents for indexing
- Chunk visualization with index settings
- Re-index after document update

### Infrastructure Graduation (When You Feel the Pain)
- **Task Queue**: Add ARQ + Redis when BackgroundTasks limitations hurt
  - Stuck documents after server restart
  - Need retry logic with backoff
  - Want job monitoring/dashboard
- **LangChain Adapter**: Add for marketability after MVP stable
  - Write `app/adapters/langchain/extractor.py`
  - Compare performance/features for blog post

### Medium Term
- Batch upload (multiple files)
- Other file types (DOCX, TXT, MD, HTML)
- URL ingestion (fetch from web)
- Folder organization within project
- Document versioning

### Long Term
- OCR for scanned PDFs
- Table extraction
- Image extraction
- Automatic metadata extraction (LLM-powered)
- Full-text search across documents
- Document comparison

---

## Critical Files Summary

**Backend - Core (9 files)**:
1. `backend/alembic/versions/XXXXX_add_documents_table.py` - Migration
2. `backend/app/models/document.py` - SQLAlchemy model
3. `backend/app/schemas/document.py` - Pydantic schemas
4. `backend/app/repositories/document_repository.py` - Database operations
5. `backend/app/services/document_service.py` - Business logic + background processing
6. `backend/app/routers/documents.py` - API endpoints
7. `backend/app/core/config.py` - Add document settings
8. `backend/app/core/dependencies.py` - DI factories for ports
9. `backend/app/main.py` - Register router

**Backend - Ports & Adapters (4 files)**:
10. `backend/app/ports/document_processing.py` - DocumentExtractor protocol
11. `backend/app/ports/storage.py` - StorageService protocol
12. `backend/app/adapters/llamaindex/extractor.py` - LlamaIndex PDF extraction
13. `backend/app/adapters/storage/local.py` - Local filesystem storage

**Frontend (9 files)**:
1. `frontend/src/types/document.ts`
2. `frontend/src/api/documents.ts`
3. `frontend/src/hooks/useDocuments.ts`
4. `frontend/src/pages/ProjectDocumentsPage.tsx`
5. `frontend/src/components/documents/DocumentUploadZone.tsx`
6. `frontend/src/components/documents/DocumentsTable.tsx`
7. `frontend/src/components/documents/DocumentViewer.tsx` - Abstraction component
8. `frontend/src/components/documents/PDFViewer.tsx` - react-pdf implementation
9. `frontend/src/components/documents/DocumentEditDialog.tsx`

**Tests (4 files)**:
1. `backend/tests/repositories/test_document_repository.py`
2. `backend/tests/services/test_document_service.py`
3. `backend/tests/adapters/test_llamaindex_extractor.py`
4. `backend/tests/routers/test_documents.py`

---

## Success Criteria

This feature is complete when:

1. ✅ Users can upload PDF documents (with drag-drop)
2. ✅ Upload returns immediately (202) with processing status
3. ✅ BackgroundTask processes documents asynchronously
4. ✅ File validation rejects invalid types and oversized files
5. ✅ Duplicate files (same checksum) are rejected per project
6. ✅ Users can view list of documents with status indicators
7. ✅ Users can view PDF in-app with extracted text alongside
8. ✅ Users can download original PDF file (when ready)
9. ✅ Users can edit document title and description
10. ✅ Users can delete documents (blocked if in index)
11. ✅ Text extraction completes and is viewable
12. ✅ Ports & Adapters architecture allows framework swap
13. ✅ All backend tests pass (including adapter tests)
14. ✅ Frontend matches existing design patterns
15. ✅ End-to-end workflow verified manually

---

## Estimated Complexity

| Phase | Effort |
|-------|--------|
| Database & Models | 2-3 hours |
| Ports & Adapters Foundation | 3-4 hours |
| Repository & Service | 3-4 hours |
| API Endpoints | 2-3 hours |
| Frontend API Layer | 2-3 hours |
| Frontend UI Components | 4-5 hours |
| Document Viewer | 3-4 hours |
| Testing & Integration | 4-5 hours |
| **Total** | **23-31 hours** |

**With ClamAV**: Add 2-3 hours for Docker setup and integration.

**Architecture Investment Note**: The Ports & Adapters pattern adds ~3-4 hours upfront but saves significant time when:
- Switching RAG frameworks (LlamaIndex → LangChain)
- Adding new document types
- Writing tests (mock at port boundary)
- Building Index feature (reuses same patterns)

**Future Migration Path**: When you experience BackgroundTasks limitations (stuck processing after restart, need retries), adding ARQ + Redis takes ~2-3 hours. Document this journey for your portfolio.

This feature establishes architectural foundations that pay dividends across RAG Admin.
