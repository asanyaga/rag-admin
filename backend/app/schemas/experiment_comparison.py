"""Pydantic schemas for experiment multi-run comparison."""
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class RunMeta(BaseModel):
    id: UUID
    name: str
    variant_label: str | None = Field(None, alias="variantLabel")
    avg_f1: float | None = Field(None, alias="avgF1")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PerRunMetrics(BaseModel):
    precision: float
    recall: float
    f1: float
    delta_f1: float | None = Field(None, alias="deltaF1")

    model_config = ConfigDict(populate_by_name=True)


class ComparisonRow(BaseModel):
    query_id: UUID = Field(..., alias="queryId")
    query_text: str = Field(..., alias="queryText")
    results: dict[str, PerRunMetrics]  # keyed by str(run_id)

    model_config = ConfigDict(populate_by_name=True)


class ExperimentComparisonResponse(BaseModel):
    experiment_id: UUID = Field(..., alias="experimentId")
    experiment_name: str = Field(..., alias="experimentName")
    baseline_run_id: UUID | None = Field(None, alias="baselineRunId")
    runs: list[RunMeta]
    rows: list[ComparisonRow]

    model_config = ConfigDict(populate_by_name=True)
