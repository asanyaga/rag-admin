# RAG Admin — Index Feature: PRD / TRD / Roadmap

**Version:** 0.2 — Revised with UX refinements and forward-looking research  
**Date:** February 2026  
**Status:** Draft  
**Scope:** Index feature design for Phase 1 (static chunking → vector/hybrid search → simple retrieval)

---

## 1. Overview

### 1.1 What This Document Covers

This document defines the Index feature for RAG Admin — the core component that transforms raw documents into searchable, retrievable knowledge. The Index is the bridge between document storage (already implemented) and evaluation (the application's primary purpose).

This document focuses on the **Phase 1 MVP**: creating indexes with configurable chunking and embedding, backed by ParadeDB for vector and full-text search. It includes forward-looking notes for subsequent phases but scopes implementation strictly to Phase 1.

### 1.2 Where Index Fits in the Product

```
User → Project → Documents (exists)
                → Indexes (this feature)     ← you are here
                → Playground (next)
                → Datasets & Evals (next)
                → Experiments (next)
```

The Index feature enables everything downstream. Without indexed, chunked, embedded documents, there is nothing to retrieve against, nothing to evaluate, and nothing to experiment with.

### 1.3 Design Principles

1. **Configuration as experimentation.** Every parameter choice (chunk size, embedding model, overlap) is a hypothesis. The system should make it easy to create multiple indexes with different configs over the same documents so users can evaluate which works best.

2. **Immutable after indexing.** Once documents have been indexed against a configuration, that configuration is read-only. This guarantees consistency — every chunk in an index was produced by the same pipeline. To try different settings, create a new index.

3. **Retrieval config lives at query time, not index time.** An index defines *how documents are processed* (chunking, embedding). *How they are searched* (vector vs. FTS vs. hybrid, top_k, RRF weights) is configured when querying or running experiments. This decoupling means one index supports many retrieval strategies without re-processing.

4. **Start simple, extend incrementally.** Phase 1 supports static chunking strategies and a small set of embedding providers. The architecture accommodates LLM-driven parsing, agentic retrieval, and multi-modal indexing in later phases without rewriting the core.

---

## 2. Product Requirements

### 2.1 User Stories

**As a RAG developer, I want to...**

- Create an index within a project, selecting which documents to include and how to chunk/embed them.
- **Select documents from my project's document list and jump directly into index creation** with those documents pre-selected, so the workflow feels natural (documents first, then configure).
- **Preview how my chunking config will split a document** before committing to a full indexing run, so I can tune chunk size and overlap with fast feedback.
- See the status of indexing (queued, processing, ready, failed) so I know when I can start querying.
- Inspect what an index contains — the chunks it produced, their metadata, and basic statistics (chunk count, average chunk size, token distribution).
- Create multiple indexes over the same documents with different configurations, so I can compare chunking strategies and embedding models during evaluation.
- Configure my embedding provider API keys at the account level and optionally override them per-project.

**As a technical consultant, I want to...**

- Quickly set up indexes for client POCs with sensible defaults so I can demonstrate value fast.
- Show clients how different chunking/embedding choices affect retrieval quality.

### 2.2 Index Configuration Parameters

When creating an index, the user configures:

| Parameter | Description | MVP Options | Default |
|---|---|---|---|
| **Name** | Human-readable identifier | Free text | Required |
| **Description** | Optional notes on purpose/config rationale | Free text | Empty |
| **Documents** | Subset of project documents to index | Multi-select from project docs | All project docs |
| **Chunking Strategy** | How documents are split | `fixed_size`, `recursive_character` | `recursive_character` |
| **Chunk Size** | Target token/character count per chunk | Integer (100–8000) | 512 |
| **Chunk Overlap** | Overlap between consecutive chunks | Integer (0–chunk_size/2) | 50 |
| **Chunk Unit** | Whether size is measured in tokens or characters | `tokens`, `characters` | `characters` |
| **Embedding Provider** | Which provider to use | `openai`, `voyage`, `local` | `openai` |
| **Embedding Model** | Specific model from the provider | Provider-dependent list | `text-embedding-3-small` |
| **Embedding Dimensions** | Vector dimensionality (if model supports it) | Integer | Model default |

**Forward-looking parameters (not in MVP, but reserved in schema):**

| Parameter | Phase | Description |
|---|---|---|
| `parsing_strategy` | Phase 3 | `static` (default), `llm_driven`, `layout_aware` |
| `metadata_extractors` | Phase 2 | LLM-powered post-chunking transforms: `questions_answered` (priority), `summary`, `keywords`, `title`, `entity`. See Phase 2 section for details. |
| `parent_child_chunking` | Phase 2 | Enable hierarchical chunk relationships |
| `multimodal` | Phase 3+ | Handle images, tables as separate indexed objects |

### 2.3 Index Lifecycle

```
┌──────────┐    ┌────────────┐    ┌──────────┐    ┌─────────┐
│  CREATED  │───▶│ PROCESSING │───▶│  READY   │    │ FAILED  │
│ (config   │    │ (chunking  │    │ (queries │    │ (error  │
│  defined) │    │  embedding)│    │  enabled)│    │  state) │
└──────────┘    └────────────┘    └──────────┘    └─────────┘
                       │                                ▲
                       └────────────────────────────────┘
```

- **CREATED**: Config is defined, documents selected. Config is still mutable at this point. No chunks exist yet.
- **PROCESSING**: Background task is running. Config becomes read-only the moment processing begins. The UI should show progress (documents processed / total).
- **READY**: All documents chunked and embedded. Index is queryable.
- **FAILED**: Processing encountered an error. The user can view the error, fix the underlying issue (e.g., invalid API key), and retry. Failed indexes can be deleted or retried.

**Key rules:**

- Once an index reaches PROCESSING, its configuration is immutable.
- Adding documents to a READY index triggers incremental processing (only new docs are chunked/embedded). Config remains unchanged.
- Removing documents from a READY index removes their chunks. No re-processing needed.
- To change chunking or embedding config, create a new index.

### 2.4 Index Inspection

Users should be able to inspect an index to understand what it contains:

- **Summary view**: Chunk count, document count, average chunk size (tokens & characters), embedding dimensions, total storage size.
- **Chunk browser**: Paginated list of chunks with their text content, source document, position in document, chunk metadata.
- **Chunk detail**: Full text, embedding vector (optionally visualized), metadata JSON, source document reference with page/section if available.

This inspection capability is critical for the evaluation workflow — users need to understand *what* was indexed to interpret *why* retrieval behaves a certain way.

---

## 3. Technical Requirements

### 3.1 Data Model

```
┌─────────────┐       ┌───────────────────┐       ┌──────────────┐
│   Project    │──1:N──│      Index         │──N:M──│   Document   │
│              │       │                   │       │              │
│ id           │       │ id                │       │ id           │
│ name         │       │ project_id (FK)   │       │ project_id   │
│ user_id      │       │ name              │       │ filename     │
└─────────────┘       │ description       │       │ content_text │
                      │ status (enum)     │       │ metadata     │
                      │ config (JSONB)    │       └──────────────┘
                      │ stats (JSONB)     │
                      │ error_message     │              │
                      │ created_at        │              │
                      │ updated_at        │              │
                      └───────────────────┘              │
                               │                         │
                          1:N  │              ┌───────────┘
                               ▼              │
                      ┌──────────────────┐    │
                      │     Chunk        │────┘ (M:1 to Document)
                      │                  │
                      │ id               │
                      │ index_id (FK)    │
                      │ document_id (FK) │
                      │ content          │
                      │ embedding (vector)│
                      │ chunk_index      │
                      │ token_count      │
                      │ char_count       │
                      │ metadata (JSONB) │
                      │ created_at       │
                      └──────────────────┘
```

**Index ↔ Document join table:**

```
┌────────────────────────┐
│   index_document       │
│                        │
│ index_id (FK)          │
│ document_id (FK)       │
│ processing_status      │
│ processed_at           │
│ error_message          │
└────────────────────────┘
```

This join table tracks per-document processing status within an index, enabling incremental adds and granular error reporting.

#### 3.1.1 The `config` JSONB Field

Storing index configuration as a JSONB column provides schema flexibility for extending configs across phases without migrations. The application layer validates config against a Pydantic schema.

```python
# Phase 1 config schema
class IndexConfig(BaseModel):
    chunking_strategy: Literal["fixed_size", "recursive_character"] = "recursive_character"
    chunk_size: int = Field(default=512, ge=100, le=8000)
    chunk_overlap: int = Field(default=50, ge=0)
    chunk_unit: Literal["tokens", "characters"] = "characters"
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int | None = None  # None = model default

    # Reserved for future phases
    parsing_strategy: Literal["static"] = "static"
    metadata_extraction: dict | None = None
```

#### 3.1.2 The `stats` JSONB Field

Computed after processing completes. Cached for fast display, recomputed on index changes.

```python
class IndexStats(BaseModel):
    total_chunks: int
    total_documents: int
    avg_chunk_size_chars: float
    avg_chunk_size_tokens: float
    min_chunk_size_chars: int
    max_chunk_size_chars: int
    total_tokens: int
    embedding_dimensions: int
    processed_at: datetime
```

### 3.2 Database Schema (SQL)

```sql
-- Index-Document many-to-many relationship
CREATE TABLE index_document (
    index_id UUID NOT NULL REFERENCES indexes(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    processing_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    processed_at TIMESTAMPTZ,
    error_message TEXT,
    PRIMARY KEY (index_id, document_id)
);

-- Chunks table with ParadeDB vector and BM25 support
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    index_id UUID NOT NULL REFERENCES indexes(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding vector NOT NULL,  -- pgvector type, dimension set per-index
    chunk_index INTEGER NOT NULL,  -- position within source document
    token_count INTEGER NOT NULL,
    char_count INTEGER NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Vector similarity search index (HNSW via pgvector)
CREATE INDEX idx_chunks_embedding ON chunks
    USING hnsw (embedding vector_cosine_ops);

-- BM25 full-text search index (via ParadeDB)
-- ParadeDB provides this via its pg_search extension
CALL paradedb.create_bm25_index(
    index_name => 'idx_chunks_bm25',
    table_name => 'chunks',
    key_field => 'id',
    text_fields => '{"content": {}}'
);

-- Standard indexes
CREATE INDEX idx_chunks_index_id ON chunks(index_id);
CREATE INDEX idx_chunks_document_id ON chunks(document_id);
```

**Note on vector dimensions:** pgvector supports dynamic dimensions per row, but HNSW indexes require uniform dimensions. Since config is immutable per index and all chunks in an index share the same embedding model, this constraint is naturally satisfied. If different indexes use different embedding models with different dimensions, they'll have separate chunks — no conflict.

### 3.3 API Design

All endpoints are project-scoped and require authentication.

#### Index CRUD

```
POST   /api/v1/projects/{project_id}/indexes           Create index
GET    /api/v1/projects/{project_id}/indexes           List indexes
GET    /api/v1/projects/{project_id}/indexes/{index_id} Get index detail
PATCH  /api/v1/projects/{project_id}/indexes/{index_id} Update index (name/description only if CREATED)
DELETE /api/v1/projects/{project_id}/indexes/{index_id} Delete index
```

#### Index Processing

```
POST   /api/v1/projects/{project_id}/indexes/{index_id}/process       Start processing
POST   /api/v1/projects/{project_id}/indexes/{index_id}/retry         Retry failed processing
GET    /api/v1/projects/{project_id}/indexes/{index_id}/status        Get processing status
```

#### Index Documents

```
POST   /api/v1/projects/{project_id}/indexes/{index_id}/documents     Add documents to index
DELETE /api/v1/projects/{project_id}/indexes/{index_id}/documents/{document_id}  Remove document
```

#### Chunk Inspection

```
GET    /api/v1/projects/{project_id}/indexes/{index_id}/chunks        List chunks (paginated)
GET    /api/v1/projects/{project_id}/indexes/{index_id}/chunks/{chunk_id}  Get chunk detail
GET    /api/v1/projects/{project_id}/indexes/{index_id}/stats         Get index statistics
```

#### Chunk Preview (Pre-Processing)

```
POST   /api/v1/projects/{project_id}/indexes/preview-chunks           Preview chunking without persisting
```

This endpoint supports the creation form's chunk preview feature. It runs the chunker in memory against a single document and returns a preview without creating any database records.

#### Request/Response Examples

**Create Index:**
```json
POST /api/v1/projects/{project_id}/indexes

{
    "name": "Product Docs — Small Chunks",
    "description": "Testing 256-char chunks with OpenAI ada-002 for comparison",
    "document_ids": ["doc-uuid-1", "doc-uuid-2"],
    "config": {
        "chunking_strategy": "recursive_character",
        "chunk_size": 256,
        "chunk_overlap": 25,
        "chunk_unit": "characters",
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small"
    },
    "auto_process": true
}
```

Note: `auto_process: true` corresponds to the "Create & Build Index" action. `auto_process: false` (or omitted) corresponds to "Save as Draft."

**Chunk Preview Request:**
```json
POST /api/v1/projects/{project_id}/indexes/preview-chunks

{
    "document_id": "doc-uuid-1",
    "config": {
        "chunking_strategy": "recursive_character",
        "chunk_size": 512,
        "chunk_overlap": 50,
        "chunk_unit": "characters"
    },
    "max_chunks": 5
}
```

**Chunk Preview Response:**
```json
{
    "total_chunks_estimate": 47,
    "avg_chunk_size_chars": 485,
    "avg_chunk_size_tokens": 121,
    "min_chunk_size_chars": 312,
    "max_chunk_size_chars": 512,
    "preview_chunks": [
        {
            "index": 0,
            "content": "The company reported revenue of $4.2B in...",
            "char_count": 510,
            "token_count": 128,
            "overlap_start_chars": 0,
            "overlap_end_chars": 50
        },
        {
            "index": 1,
            "content": "...operating expenses increased by 12%...",
            "char_count": 498,
            "token_count": 124,
            "overlap_start_chars": 50,
            "overlap_end_chars": 50
        }
    ]
}
```

The `overlap_start_chars` and `overlap_end_chars` fields tell the UI how many characters at the beginning and end of each chunk are overlap regions, enabling the highlighted overlap visualization.

**Index Status Response:**
```json
GET /api/v1/projects/{project_id}/indexes/{index_id}/status

{
    "status": "processing",
    "total_documents": 5,
    "processed_documents": 3,
    "failed_documents": 0,
    "progress_percent": 60,
    "started_at": "2026-02-06T10:30:00Z",
    "documents": [
        {"document_id": "...", "status": "completed", "chunks_created": 42},
        {"document_id": "...", "status": "processing", "chunks_created": 15},
        {"document_id": "...", "status": "pending", "chunks_created": 0}
    ]
}
```

### 3.4 Processing Pipeline

The indexing pipeline runs as a FastAPI background task. At POC scale this is sufficient; for production scale, this would migrate to a task queue (ARQ, Celery, or similar).

```
┌───────────┐    ┌───────────┐    ┌──────────┐    ┌──────────────┐    ┌──────────┐
│  Validate  │──▶│  Extract   │──▶│  Chunk   │──▶│   Embed       │──▶│  Store   │
│  Config    │   │  Text      │   │          │   │               │   │          │
│            │   │            │   │          │   │               │   │          │
│- API key   │   │- Read doc  │   │- Apply   │   │- Batch embed  │   │- Write   │
│  exists    │   │  content   │   │  strategy│   │  via provider │   │  chunks  │
│- Model     │   │- Already   │   │- Record  │   │- Rate limit   │   │  to DB   │
│  valid     │   │  extracted │   │  metadata│   │  handling     │   │- Update  │
│- Docs      │   │  at upload │   │          │   │               │   │  stats   │
│  exist     │   │            │   │          │   │               │   │          │
└───────────┘    └───────────┘    └──────────┘    └──────────────┘    └──────────┘
```

#### 3.4.1 Chunking Implementation

Phase 1 uses LangChain's text splitters (or a lightweight equivalent) for chunking:

- **`fixed_size`**: Split text into chunks of exactly `chunk_size` with `chunk_overlap` overlap. Simple, predictable. Good baseline for comparison.
- **`recursive_character`**: LangChain's `RecursiveCharacterTextSplitter` — splits on paragraph boundaries, then sentences, then words, preserving semantic coherence. This is the recommended default.

Each chunk is annotated with metadata:

```python
{
    "source_document_id": "uuid",
    "source_filename": "report.pdf",
    "chunk_index": 0,          # position in document
    "start_char": 0,           # character offset in source
    "end_char": 512,
    "page_numbers": [1, 2],    # if available from PDF extraction
}
```

#### 3.4.2 Embedding Provider Abstraction

An extensible provider pattern that starts simple:

```python
from abc import ABC, abstractmethod

class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns list of embedding vectors."""
        ...

    @abstractmethod
    def get_dimensions(self, model: str) -> int:
        """Return the output dimensions for a given model."""
        ...

    @abstractmethod
    def list_models(self) -> list[str]:
        """Return available models for this provider."""
        ...

class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI text-embedding-3-small, text-embedding-3-large, etc."""
    ...

class VoyageEmbeddingProvider(EmbeddingProvider):
    """Voyage AI embedding models."""
    ...

class LocalEmbeddingProvider(EmbeddingProvider):
    """Local models via Ollama or sentence-transformers."""
    ...
```

MVP ships with `OpenAIEmbeddingProvider`. The abstract base class ensures adding Voyage, Cohere, local models, etc. is a matter of implementing the interface — no changes to the indexing pipeline.

#### 3.4.3 Batch Processing Strategy

Embedding API calls are the bottleneck (network I/O + cost). The pipeline batches chunks for efficiency:

1. Chunk all documents first (CPU-bound, fast).
2. Collect all chunk texts.
3. Batch-embed in groups of 100–500 texts per API call (provider-dependent limits).
4. Write all chunks + embeddings to the database in a single transaction.

Error handling per document: if embedding fails for one document's chunks, mark that document as failed in `index_document`, continue with remaining documents. The index can still reach READY status with partial content, and failed documents can be retried individually.

### 3.5 Provider Key Management (BYOK)

```
┌─────────────────────────────┐
│   provider_keys              │
│                              │
│ id UUID PK                   │
│ user_id UUID FK              │
│ project_id UUID FK (nullable)│
│ provider VARCHAR(50)         │
│ api_key_encrypted TEXT       │
│ created_at TIMESTAMPTZ       │
│ updated_at TIMESTAMPTZ       │
│                              │
│ UNIQUE(user_id, project_id,  │
│        provider)             │
└─────────────────────────────┘
```

Resolution order: project-level key → account-level key → error ("no API key configured").

Keys are encrypted at rest. The application decrypts only when making provider API calls.

API endpoints:

```
POST   /api/v1/settings/provider-keys                     Set account-level key
DELETE /api/v1/settings/provider-keys/{provider}           Remove account-level key
POST   /api/v1/projects/{project_id}/settings/provider-keys   Set project-level key
DELETE /api/v1/projects/{project_id}/settings/provider-keys/{provider}  Remove
GET    /api/v1/settings/provider-keys                     List configured providers (keys masked)
```

---

## 4. Architecture Decisions

### 4.1 JSONB Config vs. Normalized Columns

**Decision:** Store index configuration as a JSONB column with Pydantic validation.

**Rationale:** The config schema will evolve significantly across phases (adding parsing strategies, metadata extraction rules, multimodal settings). JSONB avoids a migration for every new parameter. The Pydantic model provides type safety and validation at the application layer. The tradeoff is that you can't do SQL-level queries on config fields efficiently, but this isn't a requirement — indexes are always accessed by ID or listed by project.

### 4.2 Retrieval Config at Query Time

**Decision:** Index defines processing (chunking + embedding). Retrieval strategy (vector/FTS/hybrid, top_k, fusion method) is configured at query/experiment time, not baked into the index.

**Rationale:** This is the highest-leverage design decision in the system. It means:

- One index can be evaluated with many retrieval strategies without re-processing.
- Evaluation experiments can sweep across retrieval parameters cheaply.
- The "query playground" and "experiments" features have full control over retrieval without depending on index configuration.
- Users can discover that hybrid search with RRF outperforms pure vector search on their data — without having created separate indexes for each.

### 4.3 Immutable Config After Processing

**Decision:** Config is read-only once processing begins.

**Rationale:** Mutable configs would require tracking which chunks were produced under which version of the config, introducing significant complexity for marginal benefit. The alternative — creating a new index — is cheap at POC scale and maps cleanly to the comparison workflow the product encourages.

### 4.4 Background Tasks vs. Task Queue

**Decision:** Use FastAPI `BackgroundTasks` for MVP.

**Rationale:** At POC scale (dozens of documents), processing completes in seconds to minutes. A full task queue (Celery, ARQ) adds operational overhead (Redis/RabbitMQ, worker processes, monitoring) that isn't justified yet. The migration path is clean: extract the processing function into a task, wire it to a queue, done.

**When to migrate:** When processing takes > 5 minutes, when you need to process multiple indexes concurrently, or when you need crash recovery (background tasks die with the server process).

### 4.5 ParadeDB for Hybrid Search

**Decision:** Use ParadeDB's pg_search extension for BM25 alongside pgvector for dense vector search, all within PostgreSQL.

**Rationale:** This keeps the entire search stack in one database, avoiding the operational overhead of a separate search engine (Elasticsearch, Meilisearch). ParadeDB provides production-grade BM25 with the simplicity of a Postgres extension. Hybrid search (combining vector similarity and BM25 scores via RRF or weighted fusion) is implemented at query time in the application layer, giving full control over fusion strategies during evaluation.

### 4.6 No Text Preprocessing Before Chunking

**Decision:** Do not implement text preprocessing (stop word removal, stemming, punctuation stripping, etc.) in the MVP or as a default behavior.

**Rationale:** Modern embedding models (OpenAI, Voyage, etc.) are trained on natural text and handle punctuation, stop words, and casing natively. Stripping these can actually degrade embedding quality — "The company does not guarantee returns" and "company guarantee returns" (after stop word removal) have meaningfully different semantics. For BM25/full-text search, ParadeDB's pg_search handles tokenization, stemming, and stop word removal internally as part of its indexing — this doesn't need to happen in the application layer.

The one legitimate concern is **repeated header/footer text from PDFs**, which creates noise chunks. This is best addressed at the document extraction layer (upload time), not at index time. If evaluation reveals that noisy extracted text is hurting retrieval, targeted cleaning should be added to the document processing pipeline as a visible, named transform — never applied opaquely.

**Future path:** If users request preprocessing controls, expose them as optional, visible, per-index transforms in Phase 2+ so users can evaluate the impact through experiments.

### 4.7 Single Index Type, Multiple Retrieval Strategies

**Decision:** RAG Admin has one index type (chunks + embeddings + BM25). Different "ways of searching" (vector, full-text, hybrid, full-scan) are retrieval strategies configured at query/experiment time, not separate index types.

**Rationale:** Frameworks like LlamaIndex expose multiple index types (Vector Store Index, Summary Index, Tree Index, Keyword Table Index, Knowledge Graph Index). Each encodes a different retrieval strategy. In RAG Admin's architecture, most of these map to query-time configuration rather than separate indexes:

- **Vector Store Index** → Core index with pgvector. This is what RAG Admin builds.
- **Keyword Table Index** → ParadeDB BM25 on the chunks table. Already available as a retrieval strategy, not a separate index.
- **Summary Index** → "Send all chunks to the LLM without retrieval." This is a retrieval strategy option (e.g., `strategy: "full_scan"`) in the playground/experiments, not a separate index type.
- **Tree Index** → Maps to hierarchical/parent-child chunking (Phase 2). The tree traversal becomes a retrieval strategy; the data lives in the same chunks table with parent-child relationships.
- **Knowledge Graph Index** → Genuinely different infrastructure (graph layer, entity extraction, relationship storage). Phase 4+ consideration, only if consulting work surfaces use cases where vector + hybrid search falls short.

This design avoids the complexity of maintaining multiple index types and processing pipelines while preserving the ability to evaluate all these retrieval approaches against the same indexed data.

---

## 5. UI Design

### 5.1 Index List View (within a Project)

The project's index tab shows a card or table for each index:

- Name, description, status badge (created/processing/ready/failed)
- Config summary: chunking strategy, chunk size, embedding model (compact display)
- Stats: chunk count, document count (when ready)
- Actions: View, Delete, Process/Retry
- Progress indicator when processing

### 5.2 Index Creation — Entry Points

There are two ways to start creating an index:

**Primary: Start from Documents (recommended flow).** From the project's document list, the user selects one or more documents (checkboxes or shift-click), then clicks "Create Index from Selection." This pre-populates the document selection in the creation form. This covers the most common case — user has just uploaded documents and wants to index them.

**Secondary: Start from Index tab.** User clicks "New Index" from the index list view. They then use the document picker (see below) to select documents.

### 5.3 Document Selection UX

When creating an index from the Index tab (where documents aren't pre-selected), use a **dual-pane picker**:

- **Left pane:** All project documents, with search/filter, file type icons, page count, and upload date.
- **Right pane:** "Selected for this index." Click or drag to move documents between panes.
- **"Select All"** button for quick full-project indexing.

This pattern scales better than checkboxes when a project has 20+ documents and is immediately intuitive (used by Retool, Airtable, and similar data tools).

When entering from the documents list (primary flow), the right pane is pre-populated with the user's selection. They can still add/remove documents before proceeding.

### 5.4 Index Creation Form

The creation form combines configuration with a live chunk preview:

```
┌─────────────────────────────────────────────────────────┐
│  Create Index                                           │
│                                                         │
│  Name: [________________________________]               │
│  Description: [____________________________] (optional) │
│                                                         │
│  ── Documents ──────────────────────────────────────     │
│  [Dual-pane picker or pre-populated list]               │
│  3 documents selected (142 pages, 2.4 MB)               │
│                                                         │
│  ── Chunking ───────────────────────────────────────     │
│  Strategy: [recursive_character ▾]                      │
│  Chunk size: [512____] Unit: [characters ▾]             │
│  Overlap:    [50_____]                                  │
│                                                         │
│  ── Embedding ──────────────────────────────────────     │
│  Provider: [openai ▾]  Model: [text-embedding-3-small ▾]│
│  Dimensions: [auto (1536)___]                           │
│                                                         │
│  ── Chunk Preview ──────────────────────────────────     │
│  │ ~47 chunks | avg 485 chars (121 tokens)          │   │
│  │ range: 312–512 chars                             │   │
│  │                                                  │   │
│  │ Chunk 1 of report.pdf  [510 chars / 128 tokens]  │   │
│  │ ┌──────────────────────────────────────────────┐ │   │
│  │ │ The company reported revenue of $4.2B in ... │ │   │
│  │ │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │ │   │
│  │ │ (overlap region highlighted)                 │ │   │
│  │ └──────────────────────────────────────────────┘ │   │
│  │ Chunk 2 of report.pdf  [498 chars / 124 tokens]  │   │
│  │ ▶ expand                                         │   │
│  │ Chunk 3 of report.pdf  [485 chars / 121 tokens]  │   │
│  │ ▶ expand                                         │   │
│  │                                                  │   │
│  │              [Preview Chunks]                    │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  [Create & Build Index]              Save as Draft      │
└─────────────────────────────────────────────────────────┘
```

**Chunk Preview behavior:**

- Preview runs against the **first selected document only** (fast, representative).
- Shows the **first 5 chunks** as expandable cards with chunk number, character count, and token count.
- Shows a **summary bar**: estimated total chunks, average size, size range.
- **Overlap regions highlighted** in a subtle background color within each chunk's text — the single most useful visual for helping users understand what overlap does.
- Preview triggers on a **"Preview Chunks" button click**, not live. This sets clear expectations (chunking can take a moment for large documents) and avoids debouncing complexity.
- Preview is optional — user can skip straight to "Create & Build."

**Action buttons:**

- **"Create & Build Index" (primary CTA):** Creates the index config AND immediately starts background processing. This is the fast path — configure, preview, build. One action.
- **"Save as Draft" (secondary, text link):** Creates the index in CREATED state without processing. Useful when setting up multiple index configs for comparison before processing any of them. User can trigger processing later from the index detail view.

### 5.5 Index Detail View

Tabs or sections:

- **Overview**: Config summary, stats, status, timestamps.
- **Documents**: List of documents in this index with per-document processing status.
- **Chunks**: Paginated chunk browser. Search/filter chunks by content. Click to expand and see full text + metadata.
- **Config**: Full configuration displayed as a readable summary (not raw JSON).

### 5.6 Provider Key Settings

Account-level settings page with a section for each supported provider. Simple key input with masked display. Per-project overrides accessible from project settings.

---

## 6. Observability

### 6.1 Developer Observability (OTel-Based)

Index processing is instrumented with OpenTelemetry spans:

- `index.process` — top-level span for the entire processing run
  - `index.process.document` — per-document span
    - `index.process.document.chunk` — chunking step
    - `index.process.document.embed` — embedding API call

Span attributes include: `index_id`, `document_id`, `chunk_count`, `embedding_provider`, `embedding_model`, `duration_ms`, `token_count`, `error` (if any).

This feeds into whatever OTel-compatible backend you're using, and is separate from user-facing metrics.

### 6.2 User-Facing Observability (Future)

In later phases, processing metrics (time per document, token costs, error rates) could surface in the UI as part of an index's detail view. This is distinct from developer observability — it's product analytics, not infrastructure monitoring.

**Recommendation:** Keep these concerns in separate modules. Developer observability writes OTel spans. User-facing observability reads from the `stats` JSONB field and the `index_document` join table. If you later want to show OTel-derived metrics in the UI (e.g., embedding latency trends), you can bridge them via a metrics aggregation layer, but don't couple them prematurely.

---

## 7. Evaluation Integration (Forward-Looking)

This section documents how the Index feature connects to the evaluation system that will be built next. No implementation is required now, but the Index design accommodates these workflows.

### 7.1 The Evaluation Loop

```
                    ┌──────────────────────────────────┐
                    │         Evaluation Loop            │
                    │                                    │
   ┌────────┐      │  ┌───────────┐    ┌────────────┐  │    ┌──────────┐
   │ Index  │──────│──│ Retrieval │───▶│  Metrics   │──│───▶│ Compare  │
   │ (ready)│      │  │ (query    │    │ (precision │  │    │ (across  │
   │        │      │  │  config)  │    │  recall,   │  │    │  indexes │
   └────────┘      │  └───────────┘    │  MRR, NDCG)│  │    │  & configs│
                    │                   └────────────┘  │    └──────────┘
                    │                                    │
                    └──────────────────────────────────┘
```

The key insight: because retrieval config is separated from index config, an experiment can hold the index constant and sweep retrieval parameters, OR hold retrieval constant and compare indexes. This two-axis comparison is the core of the evaluation UX.

### 7.2 What the Evaluation System Will Need from Index

- **Query interface**: Given an index ID and a query string + retrieval config, return ranked chunks with scores. This is the bridge API between Index and Evaluation. It will live at query time, not in the index feature itself, but the index must be designed to support it efficiently.
- **Chunk-level ground truth**: Evaluation datasets will reference specific chunks as relevant/irrelevant for a query. The chunk ID must be stable (UUID, not positional).
- **Index metadata for comparison**: When comparing results across indexes, the UI will need to display each index's config side-by-side. The JSONB config field supports this directly.

### 7.3 Recommended Evaluation Format

For compatibility with the broader RAG evaluation ecosystem, consider adopting a format inspired by RAGAS and BEIR:

```json
{
    "queries": [
        {
            "query_id": "q1",
            "query_text": "What is the company's revenue policy?",
            "relevant_chunks": ["chunk-uuid-1", "chunk-uuid-3"],
            "relevant_passages": ["The company recognizes revenue..."],
            "expected_answer": "The company follows ASC 606..."
        }
    ]
}
```

Starting with manual creation, extending to LLM-generated synthetic datasets in a later phase. The schema should support both chunk-level relevance (for retrieval eval) and expected answers (for generation eval).

---

## 8. Agentic Evolution (Forward-Looking)

These phases are documented for architectural awareness. Each phase builds end-to-end: index config → playground → datasets → evals → experiments.

### Phase 2: Configurable Strategies, Re-Ranking & Metadata Extraction

**Index additions — Chunking:**

- Additional chunking strategies: `sentence`, `semantic` (embedding-based boundary detection), `markdown_header` (split on headings)
- Parent-child chunking: store both large context chunks and small retrieval chunks, linked

**Index additions — LLM-Powered Metadata Extraction:**

After chunking, each chunk can optionally be passed through LLM-powered extractors that generate additional metadata stored alongside the chunk. This metadata improves retrieval by bridging the gap between how documents are written (declarative statements) and how users query (questions). These extractors run post-chunking, pre-embedding, and the generated metadata can optionally be included in the text that gets embedded.

Extractors to implement (in priority order):

1. **QuestionsAnsweredExtractor** (highest priority) — Generates hypothetical questions each chunk can answer. This is essentially HyDE (Hypothetical Document Embeddings) applied at index time. When a user's query matches a generated question, retrieval improves significantly because it bridges the embedding space mismatch between questions and declarative text. Example: a chunk stating "The company reported $4.2B in revenue" would generate questions like "What was the company's revenue?" and "How much revenue did the company report?"

2. **SummaryExtractor** — Generates a concise summary of each chunk (and optionally neighboring chunks for context). Helps disambiguate chunks that are ambiguous in isolation. The summary gets stored as metadata and optionally prepended to the chunk text before embedding.

3. **KeywordExtractor** — Extracts key terms and entities from each chunk. Enables metadata-based filtering at query time ("show me only chunks about revenue") and boosts BM25 search through increased term frequency in metadata fields.

4. **TitleExtractor** — Infers a document title by analyzing multiple chunks. Useful when filenames are meaningless (like `10k-132.pdf`). The title is added to each chunk's metadata for both retrieval and display purposes.

5. **EntityExtractor** — Named entity recognition (people, organizations, dates, locations). Can use either an LLM or a lightweight NER model. Enables structured filtering at query time.

**Cost consideration:** Every extractor makes an LLM call per chunk. With 500 chunks and QuestionsAnsweredExtractor generating 3 questions each, that's 500 LLM calls for one extractor alone. This is fine at POC scale (a few dollars) but users should be able to see the cost impact and — critically — evaluate whether the metadata extraction actually improves their retrieval metrics before blindly enabling it. This is why evaluation must exist before metadata extraction is added.

**Index config extension:** The existing JSONB config field accommodates this naturally:

```python
class IndexConfig(BaseModel):
    # ... existing Phase 1 fields ...

    # Phase 2 metadata extraction
    metadata_extractors: list[MetadataExtractorConfig] | None = None

class MetadataExtractorConfig(BaseModel):
    type: Literal["questions_answered", "summary", "keywords", "title", "entity"]
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    params: dict = {}  # e.g., {"questions": 3} for QuestionsAnsweredExtractor
    include_in_embedding: bool = True  # whether to prepend to chunk text before embedding
```

**Retrieval additions (query-time, not index):**

- Re-ranking models (Cohere Rerank, cross-encoder models)
- Metadata filtering (e.g., "only search chunks from pages 1-10," "only chunks with entity X")
- Hybrid search with configurable fusion (RRF, weighted sum, learned weights)

### Phase 3: LLM-Driven Parsing & Multi-Step Retrieval

**Index additions:**

- LLM-driven parsing: use an LLM to analyze document structure and decide optimal chunking strategy per document (or per section within a document)
- Layout-aware parsing: table extraction, figure captioning, header hierarchy detection (using tools like Unstructured.io or Docling)
- Propositions indexing: decompose chunks into atomic factual statements for fine-grained retrieval

**Retrieval additions:**

- Query decomposition: break complex queries into sub-queries, retrieve for each, merge results
- HyDE (Hypothetical Document Embeddings): generate a hypothetical answer, embed that, retrieve similar real chunks
- Step-back prompting: generate a more general query to retrieve broader context

### Phase 4: Full Agentic Pipelines

**Index additions:**

- Multi-index querying: an agent decides which indexes to search based on query intent
- Dynamic indexing: indexes that update in response to query patterns (e.g., re-chunk frequently-missed documents)

**Retrieval additions:**

- Autonomous retrieval agents: iterative search-evaluate-refine loops
- Tool-augmented retrieval: agent can search the index, query a SQL database, call an API, and synthesize
- Multi-turn retrieval: agent maintains conversation state across multiple retrieval-generation cycles

### Recommendations for Agentic Parsing

Based on common use cases for document-heavy AI applications:

1. **Start with layout-aware parsing (Phase 3)** — Most documents users want to RAG over (contracts, reports, manuals, research papers) have meaningful structure that naive chunking destroys. Table extraction and heading-aware chunking provide the highest ROI. Tools like Docling (open-source, from IBM) or Unstructured.io handle this well.

2. **Add semantic chunking second** — Once layout is handled, semantic chunking (using embeddings to find natural topic boundaries) improves retrieval for narrative documents where structure is less explicit.

3. **LLM-driven parsing last** — Having an LLM decide how to chunk is powerful but expensive and slow. Reserve it for high-value use cases where other approaches fall short.

---

## 9. Implementation Roadmap

### Phase 1 Scope: Index Feature MVP

This is what gets built now. Everything is scoped to enable the first end-to-end loop: create index → inspect chunks → (soon) query in playground → evaluate.

#### Task 1: Data Model & Migrations

- Create `indexes` table with JSONB config and stats columns
- Create `index_document` join table
- Create `chunks` table with pgvector embedding column
- Create ParadeDB BM25 index on chunks.content
- Create HNSW vector index on chunks.embedding
- Create `provider_keys` table

**Prerequisites:** Existing project and document tables.

#### Task 2: Provider Key Management

- Implement encrypted key storage (Fernet or similar)
- Account-level and project-level key CRUD endpoints
- Key resolution logic (project → account → error)
- API endpoints for key management
- Basic UI: settings page with provider key inputs

**Prerequisites:** Auth system (exists).

#### Task 3: Index CRUD API

- Pydantic schemas for index creation, update, response
- IndexConfig validation (chunking params, embedding provider/model)
- CRUD endpoints (create, list, get, update, delete)
- Config immutability enforcement (reject updates if status != CREATED)
- Project-scoping and auth checks

**Prerequisites:** Task 1.

#### Task 4: Chunking Pipeline

- Implement `fixed_size` and `recursive_character` chunkers
- Chunk metadata generation (source doc, position, page numbers)
- Token counting utility (tiktoken or similar)
- **Chunk preview endpoint** — accepts a document ID + chunking config, runs the chunker in memory, returns first N chunks with statistics (total estimate, size distribution, overlap regions). No database writes.
- Unit tests for chunking strategies with edge cases

**Prerequisites:** Task 3.

#### Task 5: Embedding Provider

- Abstract `EmbeddingProvider` interface
- `OpenAIEmbeddingProvider` implementation
- Batch embedding with rate limit handling
- Provider registry (lookup provider by name)
- Integration test with real API (optional, mock-able)

**Prerequisites:** Task 2 (for API keys), Task 4.

#### Task 6: Index Processing Pipeline

- Background task orchestration (FastAPI BackgroundTasks)
- Per-document processing with status tracking
- Chunking → embedding → storage pipeline
- Error handling and partial failure support
- Status and progress endpoints
- OTel instrumentation for processing spans

**Prerequisites:** Tasks 3, 4, 5.

#### Task 7: Chunk Inspection API

- Paginated chunk listing endpoint
- Chunk detail endpoint
- Index statistics computation and caching
- Search/filter chunks by content (basic text match)

**Prerequisites:** Task 6.

#### Task 8: Index UI

- Index list view within project (cards with status badges, config summaries, stats)
- **"Create Index from Selection" entry point** on project document list (primary creation flow)
- **Index creation form** with:
  - Dual-pane document picker (with pre-population from document selection flow)
  - Chunking config fields (strategy, size, overlap, unit)
  - Embedding config fields (provider, model, dimensions)
  - **Chunk preview panel** — "Preview Chunks" button triggers preview API, displays first 5 chunks with overlap highlighting and summary stats
  - **"Create & Build Index" (primary CTA)** and **"Save as Draft" (secondary)** action buttons
- Processing status display with progress (documents processed / total)
- Index detail view with Overview, Documents, Chunks, Config tabs
- Chunk browser with pagination, search/filter, and expand/collapse
- Provider key settings page (account-level and per-project)

**Prerequisites:** Tasks 3–7, existing project UI.

#### Estimated Effort

| Task | Effort | Dependencies |
|---|---|---|
| Task 1: Data model | 1–2 days | — |
| Task 2: Provider keys | 1–2 days | — |
| Task 3: Index CRUD | 2–3 days | Task 1 |
| Task 4: Chunking + preview | 2–3 days | Task 3 |
| Task 5: Embedding | 2–3 days | Tasks 2, 4 |
| Task 6: Processing | 2–3 days | Tasks 3–5 |
| Task 7: Inspection | 1–2 days | Task 6 |
| Task 8: UI (incl. preview, dual-pane picker) | 4–6 days | Tasks 3–7 |
| **Total** | **~15–24 days** | |

### Next Features After Index (Not in Scope)

Each builds on the Index feature:

1. **Query Playground** — Interactive query interface against a ready index. Configure retrieval strategy (vector/FTS/hybrid, top_k, fusion), see ranked results with scores. This is the bridge between Index and Evaluation.

2. **Evaluation Datasets** — Create/import sets of queries with ground truth relevant chunks/answers. Start with manual creation, extend to LLM-generated synthetic data.

3. **Evaluation Runs** — Execute a retrieval strategy against a dataset, compute metrics (precision@k, recall@k, MRR, NDCG). Store results for comparison.

4. **Experiments** — Compare evaluation runs across indexes, retrieval strategies, or both. Side-by-side metrics, per-query drill-down, statistical significance.

---

## 10. Open Questions

1. **Vector dimension consistency**: Should the system validate that all chunks in an index have the same embedding dimensions before writing, or trust the provider to return consistent dimensions? Trust the provider to return consistent dimensions.

2. **Document changes**: If a user updates (re-uploads) a document that's already in a READY index, what happens? Options: ignore the update (index has the old version), automatically re-chunk the updated doc, or mark the index as stale and prompt the user. Ignore the update. Show an information message to the user.

3. **Index deletion cascade**: Deleting an index should cascade-delete all its chunks. Should it also remove any evaluation datasets/results that reference those chunks? (Likely yes for referential integrity, but this may frustrate users who want historical comparison data.) Deleting an index should only cascade to chunks.

4. **Token counting accuracy**: Should token counting use the embedding model's actual tokenizer (accurate but slower, requires per-provider logic) or a universal approximation (fast, slightly inaccurate)? Start with a unversal approximation. Can change to provider specific later.

5. **Chunk deduplication**: If the same document appears in two indexes, its chunks are stored separately (different configs may produce different chunks). Should identical chunks (same content, same embedding) across indexes be deduplicated? (Recommendation: no, keep it simple, storage is cheap.) Go with the recommendation. No deduplication.

---

## Appendix A: Glossary

| Term | Definition |
|---|---|
| **Index** | A processed, searchable representation of a set of documents. Contains chunks with embeddings. |
| **Chunk** | A segment of a document, produced by applying a chunking strategy. The unit of retrieval. |
| **Embedding** | A dense vector representation of a chunk's text, produced by an embedding model. |
| **BM25** | A probabilistic full-text search algorithm. ParadeDB provides this via pg_search. |
| **HNSW** | Hierarchical Navigable Small World — an approximate nearest neighbor algorithm for vector search. |
| **RRF** | Reciprocal Rank Fusion — a method for combining ranked lists from different search strategies. |
| **BYOK** | Bring Your Own Key — users provide their own API keys for embedding and LLM providers. |
| **HyDE** | Hypothetical Document Embeddings — generating a hypothetical answer/question and embedding that to improve retrieval. QuestionsAnsweredExtractor applies this concept at index time. |
| **Metadata Extractor** | An LLM-powered post-chunking transform that generates additional metadata (summaries, questions, keywords) for each chunk to improve retrieval quality. Phase 2 feature. |

## Appendix B: Related Documents

- Project feature PRD/TRD (existing)
- Document feature PRD/TRD (existing)
- Authentication implementation (existing)
- Observability roadmap (planned)
- Evaluation feature PRD (future — to be written after Index MVP ships)
