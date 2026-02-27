"""Pydantic schemas for experiments."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.eval_run import EvalRunResponse


# ---------------------------------------------------------------------------
# Create / Update
# ---------------------------------------------------------------------------

class ExperimentCreate(BaseModel):
    """Request to create an experiment."""
    name: str = Field(..., max_length=255)
    description: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class ExperimentUpdate(BaseModel):
    """Request to update an experiment."""
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    notes: str | None = None
    status: str | None = None
    baseline_run_id: UUID | None = Field(None, alias="baselineRunId")

    model_config = ConfigDict(populate_by_name=True)


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class ExperimentResponse(BaseModel):
    """Response for an experiment (list view)."""
    id: UUID
    name: str
    description: str | None = None
    status: str
    notes: str | None = None
    baseline_run_id: UUID | None = Field(None, alias="baselineRunId")
    baseline_run: EvalRunResponse | None = Field(None, alias="baselineRun")
    run_count: int = Field(0, alias="runCount")
    created_by: UUID = Field(..., alias="createdBy")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class VariableDiff(BaseModel):
    """What varies vs. what's constant across experiment runs."""
    varying: dict[str, list[str]] = {}
    constant: dict[str, str] = {}

    model_config = ConfigDict(populate_by_name=True)


class ExperimentDetailResponse(ExperimentResponse):
    """Detail response including runs and variable diff."""
    runs: list[EvalRunResponse] = []
    variable_diff: VariableDiff = Field(default_factory=VariableDiff, alias="variableDiff")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
