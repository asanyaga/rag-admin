"""LangGraph node functions for agent tools."""
import logging

from langgraph.types import interrupt

logger = logging.getLogger(__name__)


async def extract_node(state: dict) -> dict:
    """Extract structured data from a document using DataExtractor."""
    from app.adapters.extraction.registry import get_extractor

    logger.info("extract_node: processing document %s", state.get("document_id", "unknown"))

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


async def review_node(state: dict) -> dict:
    """Interrupt graph execution for human review."""
    logger.info("review_node: awaiting review")

    review_input = interrupt(state.get("extracted_data", {}))

    action = review_input.get("action", "reject")
    data = review_input.get("data")

    return {
        **state,
        "review_action": action,
        "reviewed_data": data if action == "edit" else state.get("extracted_data"),
        "current_step": "approved" if action in ("approve", "edit") else "rejected",
    }


async def export_node(state: dict) -> dict:
    """Export data to a project data store.

    Reads data_store_id from node config, maps state fields to table columns
    by name, and inserts a row.
    """
    from app.database import AsyncSessionLocal
    from app.repositories.data_store_repository import DataStoreRepository

    logger.info("export_node: exporting data")

    config = state.get("node_config", {})
    data_store_id = config.get("data_store_id")

    if not data_store_id:
        logger.warning("export_node: no data_store_id configured, marking as exported only")
        return {
            **state,
            "exported": True,
            "current_step": "done",
        }

    # Use reviewed_data if available (post-review), otherwise extracted_data
    data = state.get("reviewed_data") or state.get("extracted_data") or {}

    async with AsyncSessionLocal() as session:
        repo = DataStoreRepository(session)

        store = await repo.get_by_id(data_store_id, state.get("project_id"))
        if not store:
            return {
                **state,
                "error": f"Data store {data_store_id} not found",
                "exported": False,
                "current_step": "failed",
            }

        # Map state fields to table columns by name
        col_names = {col["name"] for col in store.schema_definition}
        row_data = {k: v for k, v in data.items() if k in col_names}

        # Check required columns
        for col in store.schema_definition:
            if not col.get("nullable", True) and col["name"] not in row_data:
                return {
                    **state,
                    "error": f"Required column '{col['name']}' not found in pipeline data",
                    "exported": False,
                    "current_step": "failed",
                }

        await repo.insert_row(store.table_name, store.schema_definition, row_data)
        count = await repo.count_rows(store.table_name)
        await repo.update_row_count(store.id, count)

    return {
        **state,
        "exported": True,
        "current_step": "done",
    }
