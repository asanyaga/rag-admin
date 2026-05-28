"""Pydantic schemas for evaluation runs."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.prompt_config import PromptConfig


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class EvalRunConfig(BaseModel):
    """Configuration for an evaluation run."""
    search_type: str = Field("semantic", alias="searchType")
    top_k: int = Field(5, alias="topK", ge=1, le=50)
    similarity_threshold: float = Field(0.0, alias="similarityThreshold", ge=0.0, le=1.0)

    model_config = ConfigDict(populate_by_name=True)


class ModelConfig(BaseModel):
    """Provider + model ID pair for generation/judge models."""
    provider: str
    model_id: str = Field(..., alias="modelId")

    model_config = ConfigDict(populate_by_name=True)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

class EvalRunCreate(BaseModel):
    """Request to create and run an evaluation."""
    golden_set_id: UUID = Field(..., alias="goldenSetId")
    index_id: UUID = Field(..., alias="indexId")
    name: str | None = Field(None, max_length=255)
    config: EvalRunConfig
    mode: str = Field("retrieval_only")
    generation_model: ModelConfig | None = Field(None, alias="generationModel")
    judge_model: ModelConfig | None = Field(None, alias="judgeModel")
    llm_config: PromptConfig | None = Field(None, alias="llmConfig")
    experiment_id: UUID | None = Field(None, alias="experimentId")
    variant_label: str | None = Field(None, alias="variantLabel", max_length=255)

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def validate_answer_mode_fields(self):
        if self.mode == "retrieval_and_answer":
            if not self.generation_model:
                raise ValueError("generationModel is required for retrieval_and_answer mode")
            if not self.judge_model:
                raise ValueError("judgeModel is required for retrieval_and_answer mode")
        return self


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

class EvalRunMetrics(BaseModel):
    """Aggregated metrics for an evaluation run."""
    avg_precision: float = Field(..., alias="avgPrecision")
    avg_recall: float = Field(..., alias="avgRecall")
    avg_f1: float = Field(..., alias="avgF1")
    queries_below_threshold: int = Field(..., alias="queriesBelowThreshold")

    model_config = ConfigDict(populate_by_name=True)


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class EvalRunResponse(BaseModel):
    """Response for an evaluation run."""
    id: UUID
    name: str
    golden_set_id: UUID = Field(..., alias="goldenSetId")
    golden_set_name: str = Field("", alias="goldenSetName")
    index_id: UUID = Field(..., alias="indexId")
    index_name: str = Field("", alias="indexName")
    config: dict
    status: str
    metrics: dict | None = None
    error_message: str | None = Field(None, alias="errorMessage")
    created_by: UUID = Field(..., alias="createdBy")
    created_at: datetime = Field(..., alias="createdAt")
    mode: str = Field("retrieval_only")
    generation_model: ModelConfig | None = Field(None, alias="generationModel")
    judge_model: ModelConfig | None = Field(None, alias="judgeModel")
    items_completed: int = Field(0, alias="itemsCompleted")
    failed_item_count: int = Field(0, alias="failedItemCount")
    experiment_id: UUID | None = Field(None, alias="experimentId")
    experiment_name: str | None = Field(None, alias="experimentName")
    variant_label: str | None = Field(None, alias="variantLabel")
    llm_config: dict | None = Field(None, alias="llmConfig")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------

class EvalRunProgress(BaseModel):
    """Progress of a running eval run."""
    status: str
    items_total: int = Field(..., alias="itemsTotal")
    items_completed: int = Field(..., alias="itemsCompleted")
    failed_item_count: int = Field(0, alias="failedItemCount")

    model_config = ConfigDict(populate_by_name=True)


# ---------------------------------------------------------------------------
# Per-query results
# ---------------------------------------------------------------------------

class RetrievedChunkInfo(BaseModel):
    """Info about a single retrieved chunk in eval results."""
    chunk_id: str = Field(..., alias="chunkId")
    rank: int
    score: float
    content: str
    document_id: str = Field(..., alias="documentId")
    document_name: str = Field("", alias="documentName")
    page: int | None = None
    is_relevant: bool = Field(False, alias="isRelevant")

    model_config = ConfigDict(populate_by_name=True)


class ExpectedSourceInfo(BaseModel):
    """Info about an expected source in eval results."""
    document_id: str = Field(..., alias="documentId")
    document_name: str = Field("", alias="documentName")
    locator: dict

    model_config = ConfigDict(populate_by_name=True)


class ClaimItem(BaseModel):
    """A single claim from the judge's faithfulness evaluation."""
    text: str
    label: str  # "supported" | "unsupported" | "unclear"
    source: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class EvalRunResultResponse(BaseModel):
    """Per-query result within an evaluation run."""
    id: UUID
    query_id: UUID = Field(..., alias="queryId")
    query_text: str = Field("", alias="queryText")
    precision: float
    recall: float
    f1: float
    retrieved_chunks: list[RetrievedChunkInfo] = Field(default_factory=list, alias="retrievedChunks")
    expected_sources: list[ExpectedSourceInfo] = Field(default_factory=list, alias="expectedSources")
    generated_answer: str | None = Field(None, alias="generatedAnswer")
    faithfulness_score: float | None = Field(None, alias="faithfulnessScore")
    relevance_score: float | None = Field(None, alias="relevanceScore")
    claim_breakdown: list[ClaimItem] | None = Field(None, alias="claimBreakdown")
    judge_error: str | None = Field(None, alias="judgeError")
    generation_error: str | None = Field(None, alias="generationError")
    trace_data: dict | None = Field(None, alias="traceData")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

class QueryComparisonMetrics(BaseModel):
    """Metrics for one side of a comparison."""
    precision: float
    recall: float
    f1: float

    model_config = ConfigDict(populate_by_name=True)


class QueryComparisonItem(BaseModel):
    """Per-query comparison between two runs."""
    query_id: UUID = Field(..., alias="queryId")
    query_text: str = Field("", alias="queryText")
    baseline: QueryComparisonMetrics
    challenger: QueryComparisonMetrics
    delta_f1: float = Field(..., alias="deltaF1")

    model_config = ConfigDict(populate_by_name=True)


class ComparisonSummary(BaseModel):
    """Summary statistics for a comparison between two runs."""
    avg_delta_precision: float = Field(..., alias="avgDeltaPrecision")
    avg_delta_recall: float = Field(..., alias="avgDeltaRecall")
    avg_delta_f1: float = Field(..., alias="avgDeltaF1")
    improved_queries: int = Field(..., alias="improvedQueries")
    degraded_queries: int = Field(..., alias="degradedQueries")
    unchanged_queries: int = Field(..., alias="unchangedQueries")

    model_config = ConfigDict(populate_by_name=True)


class RunComparisonResponse(BaseModel):
    """Full comparison response between two evaluation runs."""
    baseline_run: EvalRunResponse = Field(..., alias="baselineRun")
    challenger_run: EvalRunResponse = Field(..., alias="challengerRun")
    per_query_comparison: list[QueryComparisonItem] = Field(..., alias="perQueryComparison")
    summary: ComparisonSummary

    model_config = ConfigDict(populate_by_name=True)
