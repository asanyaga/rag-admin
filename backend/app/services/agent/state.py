"""LangGraph state definition for the receipt processing pipeline."""
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
