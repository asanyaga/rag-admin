"""LangGraph node functions for the receipt processing pipeline."""
import logging

from langgraph.types import interrupt

from app.adapters.extraction.registry import get_extractor
from app.services.agent.state import AgentState

logger = logging.getLogger(__name__)


async def extract_node(state: AgentState) -> AgentState:
    """Extract structured data from receipt image using DataExtractor."""
    logger.info("extract_node: processing receipt %s", state.get("receipt_id", state.get("document_id", "unknown")))

    extractor = get_extractor("llamaextract")
    if extractor is None:
        return {
            **state,
            "error": "llamaextract extractor not available",
            "current_step": "failed",
        }

    config = dict(state.get("extraction_config") or {})
    config["extraction_target"] = "PER_DOC"

    output = await extractor.extract(
        file_path=state["file_path"],
        schema=state["schema_definition"],
        config=config,
    )

    return {
        **state,
        "extracted_data": output.structured_data,
        "current_step": "review",
    }


async def review_node(state: AgentState) -> AgentState:
    """Interrupt graph execution for human review of extracted data."""
    logger.info("review_node: awaiting review for receipt %s", state.get("receipt_id", state.get("document_id", "unknown")))

    review_input = interrupt(state.get("extracted_data", {}))

    action = review_input.get("action", "reject")
    data = review_input.get("data")

    return {
        **state,
        "review_action": action,
        "reviewed_data": data if action == "edit" else state.get("extracted_data"),
        "current_step": "export" if action in ("approve", "edit") else "rejected",
    }


async def export_node(state: AgentState) -> AgentState:
    """Mark data as exported (actual DB save happens in the service layer)."""
    logger.info("export_node: exporting receipt %s", state.get("receipt_id", state.get("document_id", "unknown")))

    return {
        **state,
        "exported": True,
        "current_step": "done",
    }
