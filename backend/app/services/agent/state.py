"""LangGraph state definitions for agent pipelines."""
from typing import TypedDict


class AgentState(TypedDict, total=False):
    """State passed through the receipt processing graph."""
    receipt_id: str
    document_id: str
    file_path: str
    extraction_schema_id: str
    schema_definition: dict
    extraction_config: dict
    extracted_data: dict
    review_action: str
    reviewed_data: dict | None
    exported: bool
    error: str | None
    current_step: str


class GenericFlowState(TypedDict, total=False):
    """Minimal state for the generic flow engine.

    total=False means no keys are required. Arbitrary keys from the
    initial_state dict pass through the graph unvalidated.
    """
    current_step: str
    error: str | None
