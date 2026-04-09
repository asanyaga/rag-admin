"""Pydantic schemas for extraction evaluation runs and results."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class ExtractionEvalRunConfig(BaseModel):
    fuzzy_threshold: int = Field(85, alias="fuzzyThreshold")
    numeric_tolerance: float = Field(0.01, alias="numericTolerance")
    weights: dict[str, float] | None = None

    model_config = ConfigDict(populate_by_name=True)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

class ExtractionEvalRunCreate(BaseModel):
    ground_truth_set_id: UUID = Field(..., alias="groundTruthSetId")
    name: str | None = Field(None, max_length=255)
    config: ExtractionEvalRunConfig | None = None

    model_config = ConfigDict(populate_by_name=True)


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class ExtractionEvalRunResponse(BaseModel):
    id: UUID
    project_id: UUID = Field(..., alias="projectId")
    ground_truth_set_id: UUID = Field(..., alias="groundTruthSetId")
    ground_truth_set_name: str = Field("", alias="groundTruthSetName")
    name: str
    config: dict
    status: str
    metrics: dict | None = None
    error_message: str | None = Field(None, alias="errorMessage")
    items_completed: int = Field(0, alias="itemsCompleted")
    items_total: int = Field(0, alias="itemsTotal")
    created_by: UUID = Field(..., alias="createdBy")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

class ExtractionEvalResultResponse(BaseModel):
    id: UUID
    eval_run_id: UUID = Field(..., alias="evalRunId")
    extraction_result_id: UUID = Field(..., alias="extractionResultId")
    ground_truth_item_id: UUID = Field(..., alias="groundTruthItemId")
    document_id: UUID = Field(..., alias="documentId")
    document_title: str = Field("", alias="documentTitle")
    overall_score: float = Field(..., alias="overallScore")
    field_scores: dict = Field(..., alias="fieldScores")
    line_items_score: dict | None = Field(None, alias="lineItemsScore")
    expected_data: dict | list | None = Field(None, alias="expectedData")
    predicted_data: dict | list | None = Field(None, alias="predictedData")
    evaluation_metadata: dict | None = Field(None, alias="evaluationMetadata")
    created_at: datetime = Field(..., alias="createdAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
