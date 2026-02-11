# RAG Admin — Answer Playground Design Document

## Overview

This document outlines the design for adding answer generation capabilities to the RAG Admin Index Playground. The answer playground extends the existing retrieval playground by adding an LLM generation layer on top of retrieved chunks, enabling users to see the full RAG pipeline output — from query → retrieval → answer — in a single interactive surface.

The design follows an incremental approach: start minimal, validate the core loop, then progressively layer in sophistication.

---

## 1. Playground UI — Extending the Retrieval Playground

### Recommendation: "Answer Mode" Toggle with Unified View

Rather than a separate tab, add a toggle within the existing Playground tab that switches between **Retrieval Mode** (current behavior) and **Answer Mode** (retrieval + generation). When Answer Mode is active, the playground shows both the generated answer and the retrieved chunks that fed into it.

### Layout Options

#### Option A: Stacked Layout (Recommended for v1)

```
┌─────────────────────────────────────────────────────────┐
│  PARAMETERS          │  Query Input                     │
│  ───────────         │  [________________________] [Go] │
│  Mode: [Retrieval|Answer]                               │
│  Search Type         │                                  │
│  Top-K               │  ┌─ ANSWER ──────────────────┐   │
│  Threshold           │  │ The fund reported a 12.3%  │   │
│                      │  │ return in Q3... [1][2]     │   │
│  ── LLM (if Answer)  │  └───────────────────────────┘   │
│  Provider/Model      │                                  │
│  Temperature         │  ┌─ RETRIEVED CHUNKS ────────┐   │
│  Instructions        │  │ [1] chunk content...       │   │
│                      │  │ [2] chunk content...       │   │
│                      │  │ [3] chunk content...       │   │
│                      │  └───────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

The answer panel sits above the chunk results, clearly showing what the LLM produced and what it was given. Chunks are numbered and clickable, with citation references in the answer mapping to chunk numbers below.

**Pros:** Simple, linear reading flow (question → answer → evidence). No horizontal scrolling. Works well on narrower screens. Clear visual hierarchy — the answer is what the user asked for, chunks are supporting evidence.

**Cons:** Requires scrolling to see chunks if the answer is long. Can't view answer and a specific chunk side-by-side without scrolling.

#### Option B: Side-by-Side Layout

```
┌──────────────────────────────────────────────────────────┐
│  PARAMETERS     │  ANSWER                │  CHUNKS       │
│  ───────────    │  The fund reported...  │  [1] chunk... │
│  Mode toggle    │  [1][2]                │  [2] chunk... │
│  Search params  │                        │  [3] chunk... │
│  LLM params     │                        │               │
└──────────────────────────────────────────────────────────┘
```

**Pros:** Can see answer and source chunks simultaneously. Better for explainability demos — client can see the evidence right alongside the answer. Clicking a citation could highlight the corresponding chunk.

**Cons:** Three-column layout gets tight, especially with the parameter panel. May require wider viewport. More complex responsive behavior.

#### Option C: Collapsible Evidence Drawer

Same stacked layout as Option A, but chunks are collapsed by default behind a "Show N sources" toggle. Clicking a citation `[1]` expands and scrolls to that specific chunk.

**Pros:** Clean, chat-like answer experience. Reduces visual noise when the user just wants to see the answer. Still provides full transparency on demand.

**Cons:** Evidence is hidden by default, which somewhat undermines the explainability goal. Extra click to inspect sources.

### Recommendation

**Start with Option A (Stacked)** for v1 — it's the simplest to implement, preserves the existing chunk display, and naturally extends the current layout. Plan a migration path to Option B for client-facing demo scenarios, potentially as a layout toggle. Option C works well as an enhancement on top of either A or B for the citation-click-to-expand behavior.

### Behavioral Details

When the user toggles to Answer Mode, the LLM parameter section appears in the left panel below the retrieval parameters. When they run a query, the system first performs retrieval (identical to current behavior), then streams the LLM answer above the chunk results. The chunk results should always be visible in Answer Mode — this is the key differentiator from a generic chat interface.

In Retrieval Mode, the playground behaves exactly as it does today. No LLM parameters shown, no answer panel.

---

## 2. LLM Backend — Getting Started Simply

### Recommendation: Thin Adapter Pattern

Build a minimal abstraction that handles the core need (send messages, stream tokens back) without trying to be a general-purpose LLM framework. Design it so it can be **replaced entirely** by a mature framework later without changing the API contract.

### Architecture

```
┌─────────────────────────┐
│   FastAPI Router         │  POST /api/v1/indexes/{id}/playground/answer
│   (Streaming endpoint)   │  SSE response
└───────────┬─────────────┘
            │
┌───────────▼─────────────┐
│   AnswerService          │  Orchestrates: retrieve → build prompt → stream
│   (Application layer)    │  No LLM details here
└───────────┬─────────────┘
            │
┌───────────▼─────────────┐
│   LLMPort (Protocol)     │  async def stream_completion(messages, config) -> AsyncIterator[str]
│   (Interface/port)       │  async def complete(messages, config) -> CompletionResult
└───────────┬─────────────┘
            │
  ┌─────────┼─────────┐
  ▼         ▼         ▼
OpenAI   Anthropic   Ollama
Adapter   Adapter    Adapter
```

### The LLM Port (Interface)

```python
from typing import Protocol, AsyncIterator
from dataclasses import dataclass

@dataclass
class LLMConfig:
    provider: str          # "openai" | "anthropic" | "ollama"
    model: str             # "gpt-4o" | "claude-sonnet-4-20250514" | "llama3"
    temperature: float = 0.0
    max_tokens: int = 1024

@dataclass
class CompletionResult:
    content: str
    usage: TokenUsage       # prompt_tokens, completion_tokens, total_tokens
    latency_ms: float
    model: str
    provider: str

@dataclass
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class LLMPort(Protocol):
    async def stream_completion(
        self,
        messages: list[dict],
        config: LLMConfig
    ) -> AsyncIterator[str]:
        """Yields content tokens as they arrive."""
        ...

    async def complete(
        self,
        messages: list[dict],
        config: LLMConfig
    ) -> CompletionResult:
        """Non-streaming completion with full result metadata."""
        ...
```

### Adapter Implementation (OpenAI Example)

```python
class OpenAIAdapter:
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

    async def stream_completion(self, messages, config):
        stream = await self.client.chat.completions.create(
            model=config.model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def complete(self, messages, config):
        start = time.monotonic()
        response = await self.client.chat.completions.create(
            model=config.model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
        latency = (time.monotonic() - start) * 1000
        return CompletionResult(
            content=response.choices[0].message.content,
            usage=TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            ),
            latency_ms=latency,
            model=config.model,
            provider="openai",
        )
```

### Provider Registry

```python
class LLMRegistry:
    """Simple registry — no magic, easy to replace later."""

    def __init__(self):
        self._adapters: dict[str, LLMPort] = {}

    def register(self, provider: str, adapter: LLMPort):
        self._adapters[provider] = adapter

    def get(self, provider: str) -> LLMPort:
        if provider not in self._adapters:
            raise ValueError(f"Provider '{provider}' not configured")
        return self._adapters[provider]
```

### Why This Works for Now and Later

This pattern is intentionally thin. Each adapter is ~50 lines. The `LLMPort` protocol defines the contract, so when you're ready to swap in LiteLLM, LangChain's chat models, or a custom framework, you either make that framework conform to `LLMPort` or replace the registry with whatever that framework provides. The `AnswerService` never knows or cares.

What you're **not** building: retry logic, rate limiting, fallback chains, prompt versioning, token counting, conversation memory. All of that belongs in whatever mature framework you adopt later. For now, the adapters are pass-through wrappers around each provider's SDK.

### Provider Key Reuse

You mentioned there's an existing feature for managing provider keys (used for embeddings). The LLM adapters should pull from the same key storage. When the user selects "OpenAI / gpt-4o" in the playground, the system looks up their stored OpenAI key and initializes the adapter. No duplicate key management.

---

## 3. Prompt & Instruction Control — Progressive Sophistication

### Phase 1: Freeform Instructions Field (v1)

A single text area in the parameter panel labeled **"Instructions"** with placeholder text like *"e.g., Answer as a financial analyst. Be concise."*

Behind the scenes, the system constructs the prompt:

```python
def build_rag_prompt(query: str, chunks: list[Chunk], instructions: str | None = None) -> list[dict]:
    system_parts = [
        "Answer the user's question using ONLY the provided context.",
        "Cite sources using [1], [2], etc. corresponding to the chunk numbers.",
        "If the context doesn't contain enough information, say so.",
    ]
    if instructions:
        system_parts.append(f"\nAdditional instructions: {instructions}")

    context = "\n\n".join(
        f"[{i+1}] {chunk.content}" for i, chunk in enumerate(chunks)
    )

    return [
        {"role": "system", "content": "\n".join(system_parts)},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
    ]
```

This gives the user control without exposing prompt engineering complexity. The core RAG behavior (use context, cite sources, acknowledge gaps) is baked in.

### Phase 2: Prompt Template Presets

Introduce named presets that configure the system prompt:

| Preset | Behavior |
|--------|----------|
| **Default** | Balanced, cited answer |
| **Concise** | Short, direct answers with citations |
| **Detailed** | Comprehensive analysis with all relevant context |
| **Extract** | Structured extraction — returns data points, not prose |
| **Explain** | Explains concepts found in documents, educational tone |

The user picks a preset and optionally adds their own instructions on top. Presets are stored as prompt templates in the database.

### Phase 3: Full Prompt Template Editor

A dedicated prompt template management UI where users can:

- Create, edit, clone, and version prompt templates
- Use template variables (`{{context}}`, `{{query}}`, `{{instructions}}`)
- Test templates in the playground before using them in evaluations
- Share templates across projects

This is a significant feature and should be its own design cycle. The key architectural decision for v1 is: **store the constructed prompt alongside every playground result** so you have a record of what was sent, enabling future template-based comparisons even for results generated before templates existed.

### Migration Path

The `build_rag_prompt` function is the seam. In Phase 1, it's hardcoded. In Phase 2, it reads from preset configs. In Phase 3, it renders a user-defined template. The `AnswerService` always calls the same function signature, so the prompt construction logic is swappable without touching the service or adapters.

---

## 4. Citations & Explainability — From Simple to Sophisticated

### Phase 1: Numbered Inline Citations (v1)

The prompt instructs the LLM to cite sources using `[1]`, `[2]`, etc. The frontend parses these from the streamed answer and renders them as clickable badges. Clicking `[1]` scrolls to or highlights chunk `[1]` in the results panel below.

```
Answer: The fund's Q3 return was 12.3% [1], outperforming the
benchmark by 2.1 percentage points [2].

Retrieved Chunks:
┌──────────────────────────────────────────────────┐
│ [1] Score: 0.89 | Page 14                        │
│ "In Q3 2024, Acorn REIT Fund delivered a total   │
│  return of 12.3%, driven primarily by..."         │  ← highlighted when [1] clicked
│──────────────────────────────────────────────────│
│ [2] Score: 0.84 | Page 16                        │
│ "Against the MSCI benchmark return of 10.2%,     │
│  the fund outperformed by 210 basis points..."    │
└──────────────────────────────────────────────────┘
```

**Implementation:** Parse `[N]` patterns from the response text using a simple regex. Render them as styled `<button>` elements that trigger scroll-to behavior. No LLM-side structured output needed — just prompt engineering.

**Known limitations:** LLMs sometimes hallucinate citation numbers, cite the wrong chunk, or skip citations. This is acceptable for a playground — the user can see the chunks and judge for themselves.

### Phase 2: Verified Citations

Post-process the answer to validate citations:

1. For each `[N]` reference, extract the claim being made
2. Check if chunk `[N]` actually supports that claim (using simple heuristic overlap or a lightweight LLM call)
3. Color-code citations: green (verified), yellow (partial match), red (unsupported)

This adds cost per query but dramatically improves trust for client demos.

### Phase 3: Chunk Highlighting + Source Viewer

When a citation is clicked, open the original document (PDF viewer) scrolled to the relevant page/section, with the specific passage highlighted. This requires chunk metadata to include page numbers and character offsets (which your chunking pipeline should already capture or can be extended to capture).

This is the "show me exactly where this came from" experience that differentiates RAG Admin for client demonstrations.

### Architectural Note

All citation phases work with the same underlying data: chunks with metadata (score, page, position) and an answer with embedded references. Phase 1 renders this minimally. Phases 2-3 enrich the rendering. No schema changes needed between phases — just richer frontend behavior and optional post-processing.

---

## 5. Answer Evaluation — Future Integration

This section is deliberately brief since it's a follow-on feature, but the architectural decisions made now should support it.

### Design Hooks for Later

**Store every playground answer result:**

```python
@dataclass
class PlaygroundAnswerResult:
    id: str
    index_id: str
    query: str
    instructions: str | None
    retrieval_config: RetrievalConfig      # search_type, top_k, threshold
    llm_config: LLMConfig                  # provider, model, temperature
    prompt_messages: list[dict]            # exact messages sent to LLM
    chunks_retrieved: list[ChunkResult]    # what retrieval returned
    answer: str                            # generated answer
    citations_parsed: list[int]            # which chunk numbers were cited
    usage: TokenUsage
    latency_ms: float
    created_at: datetime
```

This record becomes the raw material for evaluation. When the answer evaluation feature is built, golden answers can be compared against stored playground results using metrics like ROUGE, semantic similarity, faithfulness (does the answer stay grounded in chunks), and citation accuracy.

**Evaluation progression:**

1. **Now:** Store results, no formal evaluation
2. **Next:** Manual thumbs-up/thumbs-down on playground answers (lightweight quality signal)
3. **Later:** Golden answer sets, automated metrics, comparison across configurations

---

## 6. Observability — User-Level vs. Infrastructure-Level

### The Two-Layer Model

This is an important architectural distinction. Infrastructure observability (is the server healthy, what's the p99 latency, are there errors) is fundamentally different from user-level observability (how much did this query cost me, how fast was the response, how many tokens did I use today).

```
┌──────────────────────────────────────────────────┐
│                  RAG Admin App                    │
│                                                   │
│  ┌─────────────────────────────────────────────┐  │
│  │  User-Level Observability                   │  │
│  │  (Application concern)                      │  │
│  │                                             │  │
│  │  - Token usage per query                    │  │
│  │  - Cost per query / per day                 │  │
│  │  - Response latency (user-perceived)        │  │
│  │  - Retrieval scores                         │  │
│  │  - Model/provider used                      │  │
│  │  - Error rates on their queries             │  │
│  │                                             │  │
│  │  Storage: Application DB (PostgreSQL)       │  │
│  │  Surface: In-app dashboards, per-query UI   │  │
│  └─────────────────────────────────────────────┘  │
│                                                   │
│  ┌─────────────────────────────────────────────┐  │
│  │  Infrastructure Observability               │  │
│  │  (Operator concern)                         │  │
│  │                                             │  │
│  │  - Request throughput / error rates          │  │
│  │  - System latency (actual, decomposed)      │  │
│  │  - DB query performance                     │  │
│  │  - LLM provider availability                │  │
│  │  - Memory / CPU / disk                      │  │
│  │  - Queue depth (if async processing)        │  │
│  │                                             │  │
│  │  Emission: OpenTelemetry SDK                │  │
│  │  Backend: Pluggable (Jaeger, Grafana, etc.) │  │
│  └─────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

### Why Separate Them

**Different audiences:** Infrastructure metrics are for you (the operator). User metrics are for RAG Admin's users (the people building RAG pipelines). Mixing them creates noise — a user doesn't need to know about garbage collection pauses, and you don't need per-user token counts in your Grafana dashboards.

**Different storage:** User-level metrics belong in the application database because they need to be queryable per-user, per-project, per-index. They're first-class domain data. Infrastructure metrics belong in a time-series backend (whatever you plug into OTel) because they're high-cardinality, time-windowed, and disposable.

**Different lifecycles:** User metrics are retained as long as the user's data exists. Infrastructure metrics are typically retained for days/weeks with downsampling.

### User-Level Observability — Incremental Build

#### Phase 1: Per-Query Metrics in Playground (v1)

Display a small metrics bar below each answer in the playground:

```
┌──────────────────────────────────────────────────┐
│ ⏱ 1.2s  │  📊 342 in / 189 out tokens  │  gpt-4o │
└──────────────────────────────────────────────────┘
```

Data comes directly from the `CompletionResult` returned by the LLM adapter. No additional storage needed — it's rendered inline and stored as part of the `PlaygroundAnswerResult`.

#### Phase 2: Query History with Metrics

A simple table view accessible from the playground showing recent queries with their metrics. Useful for comparing "that query was slow, this one was fast — what changed?"

#### Phase 3: Usage Dashboard

An aggregated view per project/index showing total token usage over time, cost estimates (based on known per-token pricing for each model), and common query patterns. This is where you'd surface things like "you've spent $4.23 on GPT-4o queries this week across 47 runs."

#### Phase 4: Pipeline Trace View

A detailed trace showing the full breakdown of a single query: retrieval time, embedding time, LLM time, total time, with each step shown as a span. This is where user-level and infrastructure observability can share data — you emit OTel spans for each step, and the user-level view reads a simplified version of the same trace.

### Infrastructure Observability — OTel Integration

You already have auto-instrumentation at the frontend and FastAPI level. For the answer feature, add manual spans for the key steps:

```python
from opentelemetry import trace

tracer = trace.get_tracer("ragadmin.answer")

async def generate_answer(query, index_id, config):
    with tracer.start_as_current_span("answer.pipeline") as span:
        span.set_attribute("index_id", index_id)
        span.set_attribute("llm.provider", config.provider)
        span.set_attribute("llm.model", config.model)

        with tracer.start_as_current_span("answer.retrieval"):
            chunks = await retrieve(query, index_id, retrieval_config)

        with tracer.start_as_current_span("answer.prompt_build"):
            messages = build_rag_prompt(query, chunks, instructions)

        with tracer.start_as_current_span("answer.llm_call") as llm_span:
            result = await llm.complete(messages, config)
            llm_span.set_attribute("llm.tokens.prompt", result.usage.prompt_tokens)
            llm_span.set_attribute("llm.tokens.completion", result.usage.completion_tokens)
            llm_span.set_attribute("llm.latency_ms", result.latency_ms)

        return result
```

These spans flow to whatever OTel backend you configure. The user-level metrics (token counts, latency) are extracted from the same `CompletionResult` and written to PostgreSQL. Same data, two destinations, two purposes.

### OTel Semantic Conventions

Use the emerging [GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) for LLM-related attributes when they're relevant. This keeps your traces portable across backends:

- `gen_ai.system` → provider name
- `gen_ai.request.model` → model string
- `gen_ai.usage.prompt_tokens` → input tokens
- `gen_ai.usage.completion_tokens` → output tokens

---

## 7. Streaming — SSE Implementation

### Recommendation: Server-Sent Events (SSE)

SSE is the right choice for this use case: unidirectional server-to-client streaming, works over HTTP, no WebSocket complexity, and aligns with how OpenAI and Anthropic deliver their own streaming APIs.

### Options Considered

| Approach | Pros | Cons |
|----------|------|------|
| **SSE (recommended)** | Simple, HTTP-native, browser EventSource API, works behind most proxies, matches LLM provider patterns | Unidirectional only, reconnection handling needed |
| **WebSocket** | Bidirectional, persistent connection | Overkill for request/response streaming, more complex server setup, proxy issues |
| **Long polling** | Simplest to implement | High latency, wasteful, poor UX |
| **Chunked transfer** | No special protocol | Hard to parse incrementally, no built-in reconnection |

### Backend Implementation

```python
from fastapi.responses import StreamingResponse

@router.post("/indexes/{index_id}/playground/answer")
async def playground_answer(
    index_id: str,
    request: PlaygroundAnswerRequest,
):
    async def event_stream():
        # Phase 1: Retrieval (send chunks as a batch event)
        chunks = await retrieval_service.search(index_id, request.query, request.retrieval_config)
        yield f"event: chunks\ndata: {json.dumps([c.dict() for c in chunks])}\n\n"

        # Phase 2: Build prompt
        messages = build_rag_prompt(request.query, chunks, request.instructions)

        # Phase 3: Stream LLM response
        llm = llm_registry.get(request.llm_config.provider)
        async for token in llm.stream_completion(messages, request.llm_config):
            yield f"event: token\ndata: {json.dumps({'content': token})}\n\n"

        # Phase 4: Send final metadata
        # (token counts available from stream close or separate call)
        yield f"event: done\ndata: {json.dumps({'usage': usage.dict(), 'latency_ms': latency})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

### Frontend Consumption

```typescript
const response = await fetch(`/api/v1/indexes/${indexId}/playground/answer`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(requestBody),
});

const reader = response.body!.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const text = decoder.decode(value);
  // Parse SSE events and update UI state
  for (const event of parseSSEEvents(text)) {
    switch (event.type) {
      case 'chunks':
        setChunks(JSON.parse(event.data));
        break;
      case 'token':
        setAnswer(prev => prev + JSON.parse(event.data).content);
        break;
      case 'done':
        setMetrics(JSON.parse(event.data));
        break;
    }
  }
}
```

### Streaming UX Details

The stream delivers events in phases, and the UI should reflect this:

1. **"Retrieving..."** — spinner while chunks are fetched
2. **Chunks appear** — retrieved results render in the chunk panel
3. **"Generating answer..."** — brief transition
4. **Tokens stream in** — answer text appears token-by-token in the answer panel
5. **Metrics appear** — token count, latency shown after stream completes

If the user cancels mid-stream (navigates away, clicks "Stop"), the frontend should abort the fetch and the backend should detect the closed connection and stop the LLM call to avoid unnecessary token spend.

### Streaming + Token Usage Tradeoff

Most LLM providers only report token usage after the stream completes (OpenAI) or in a final event (Anthropic). This means the metrics bar appears after the answer finishes streaming, not during. This is acceptable and expected.

For the non-streaming `complete()` method (used by evaluation runs where streaming isn't needed), token counts are available immediately in the response.

---

## 8. Implementation Phases

### Phase 1: Core Answer Loop (v1)

**Goal:** User can toggle to Answer Mode, pick a provider/model, type a query, and see a streamed answer with inline `[N]` citations above the retrieved chunks.

**Backend:**
- `LLMPort` protocol + OpenAI adapter (start with one provider)
- `LLMRegistry` for provider management
- `build_rag_prompt()` with hardcoded RAG system prompt + optional instructions
- SSE streaming endpoint
- `PlaygroundAnswerResult` model stored in PostgreSQL

**Frontend:**
- Answer Mode toggle in playground
- LLM parameter section (provider, model, temperature, instructions)
- Streaming answer panel with `[N]` citation parsing
- Click-to-scroll citation behavior
- Per-query metrics bar (latency, tokens, model)

**Not included:** Prompt presets, citation verification, usage dashboards, evaluation integration.

### Phase 2: Multi-Provider + Prompt Presets

- Anthropic and Ollama adapters
- Prompt template presets (concise, detailed, extract, etc.)
- Query history with metrics in playground
- Basic usage aggregation per project

### Phase 3: Rich Explainability + Evaluation Hooks

- Citation verification (green/yellow/red)
- Source document viewer with passage highlighting
- Thumbs up/down on playground answers
- Golden answer sets in evaluation workflow
- Usage dashboard with cost estimates

### Phase 4: Full Template System + Pipeline Traces

- Prompt template editor with versioning
- Template variables and sharing
- Pipeline trace view (user-level)
- Answer quality metrics in evaluation runs

---

## 9. API Contract

### Request

```
POST /api/v1/indexes/{index_id}/playground/answer
Content-Type: application/json
Accept: text/event-stream

{
  "query": "What was the Q3 return?",
  "instructions": "Answer as a financial analyst. Be concise.",
  "retrieval_config": {
    "search_type": "hybrid",
    "top_k": 5,
    "threshold": 0.0
  },
  "llm_config": {
    "provider": "openai",
    "model": "gpt-4o",
    "temperature": 0.0,
    "max_tokens": 1024
  }
}
```

### SSE Events

```
event: chunks
data: [{"id": "...", "content": "...", "score": 0.89, "metadata": {...}}, ...]

event: token
data: {"content": "The"}

event: token
data: {"content": " fund"}

event: token
data: {"content": "'s Q3"}

...

event: done
data: {"usage": {"prompt_tokens": 342, "completion_tokens": 189, "total_tokens": 531}, "latency_ms": 1243, "result_id": "..."}

event: error
data: {"error": "Provider returned 429: rate limited", "code": "llm_rate_limit"}
```

---

## 10. Key Decisions Summary

| Decision | Recommendation | Rationale |
|----------|---------------|-----------|
| UI layout | Stacked (answer above chunks) | Simplest, extends current layout naturally |
| LLM abstraction | Thin adapter + protocol | Easy to replace later, no framework lock-in |
| First provider | OpenAI | Most common, simplest SDK, likely already keyed |
| Prompt control (v1) | Freeform instructions field | Low complexity, high flexibility |
| Citations (v1) | Prompt-based `[N]` with click-to-scroll | No structured output needed, good enough for playground |
| Streaming | SSE | HTTP-native, matches LLM provider patterns |
| Observability split | User metrics in Postgres, infra metrics via OTel | Different audiences, lifecycles, query patterns |
| Result storage | Store everything from day one | Enables evaluation integration without migration |
