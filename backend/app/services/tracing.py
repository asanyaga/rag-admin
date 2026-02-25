"""Trace data models for query pipeline observability."""

from pydantic import BaseModel, Field


class SpanMetrics(BaseModel):
    """Typed metrics bag. Each span_type populates relevant fields."""

    latency_ms: float | None = Field(None, alias="latencyMs")
    token_count: int | None = Field(None, alias="tokenCount")
    char_count: int | None = Field(None, alias="charCount")
    embedding_dimensions: int | None = Field(None, alias="embeddingDimensions")
    result_count: int | None = Field(None, alias="resultCount")
    similarity_threshold: float | None = Field(None, alias="similarityThreshold")
    top_k: int | None = Field(None, alias="topK")
    prompt_tokens: int | None = Field(None, alias="promptTokens")
    completion_tokens: int | None = Field(None, alias="completionTokens")
    total_tokens: int | None = Field(None, alias="totalTokens")
    model: str | None = None
    provider: str | None = None

    model_config = {"populate_by_name": True}


class Span(BaseModel):
    """A single pipeline step in a query trace."""

    id: str
    parent_id: str | None = Field(None, alias="parentId")
    span_type: str = Field(alias="spanType")
    name: str
    input: dict | list | str | None = None
    output: dict | list | str | None = None
    metrics: SpanMetrics = SpanMetrics()
    started_at: str = Field(alias="startedAt")
    ended_at: str | None = Field(None, alias="endedAt")
    duration_ms: float | None = Field(None, alias="durationMs")
    order: int = 0
    status: str = "ok"
    error: str | None = None
    children: list["Span"] = []

    model_config = {"populate_by_name": True}


class QueryTrace(BaseModel):
    """Complete trace of a query execution."""

    trace_id: str = Field(alias="traceId")
    query: str
    search_type: str = Field(alias="searchType")
    total_duration_ms: float = Field(alias="totalDurationMs")
    spans: list[Span]
    created_at: str = Field(alias="createdAt")

    model_config = {"populate_by_name": True}
