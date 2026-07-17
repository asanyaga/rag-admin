"""Response schemas for parse-agent runs (camelCase, mirrors parse_run schemas).

`app/schemas/parse_run.py` does not export a reusable `CamelModel` — it hand-aliases
each field individually (`Field(..., alias="camelCaseName")`) on top of
`ConfigDict(from_attributes=True, populate_by_name=True)`. Rather than hand-alias every
field here, this module defines a local `CamelModel` base that reuses that same
`ConfigDict` shape plus pydantic's built-in `to_camel` alias generator, so snake_case
attributes still serialize as camelCase on the wire.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base model that serializes snake_case attributes as camelCase."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class ParseAgentRunStepResponse(CamelModel):
    id: UUID
    seq: int
    node: str
    phase: str
    status: str
    input_keys: list[str]
    output_keys: list[str]
    state_delta: dict
    message: str | None
    duration_ms: int | None
    created_at: datetime


class ParseAgentRunSummary(CamelModel):
    id: UUID
    project_id: UUID
    source_document_id: UUID
    status: str
    started_at: datetime
    finished_at: datetime | None
    error: str | None


class ParseAgentRunDetailResponse(CamelModel):
    run: ParseAgentRunSummary
    steps: list[ParseAgentRunStepResponse]
    graph_nodes: list[str]


class ParseAgentRunCreatedResponse(CamelModel):
    run_id: UUID
