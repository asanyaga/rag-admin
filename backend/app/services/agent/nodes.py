"""LangGraph node functions for agent tools."""
import logging

from langgraph.types import interrupt

logger = logging.getLogger(__name__)


async def extract_node(state: dict, *, node_config: dict | None = None) -> dict:
    """Extract structured data from a document using DataExtractor."""
    from app.adapters.extraction.registry import get_extractor
    from app.config import settings

    logger.info("extract_node: processing document %s", state.get("document_id", "unknown"))

    credentials = {}
    if settings.LLAMA_CLOUD_KEY:
        credentials["api_key"] = settings.LLAMA_CLOUD_KEY

    extractor = get_extractor("llamaextract", credentials)

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


async def review_node(state: dict, *, node_config: dict | None = None) -> dict:
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


async def export_node(state: dict, *, node_config: dict | None = None) -> dict:
    """Export data to a project data store.

    Supports explicit field_mapping with dot-path notation and array fan-out.
    Falls back to name-matching if no field_mapping is configured.
    """
    from app.database import AsyncSessionLocal
    from app.repositories.data_store_repository import DataStoreRepository
    from app.services.agent.field_mapper import flatten_to_rows

    logger.info("export_node: exporting data")

    config = state.get("node_config", {})
    data_store_id = config.get("data_store_id")

    if not data_store_id:
        logger.warning("export_node: no data_store_id configured, marking as exported only")
        return {
            **state,
            "exported": True,
            "rows_exported": 0,
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
                "rows_exported": 0,
                "current_step": "failed",
            }

        field_mapping = config.get("field_mapping")

        if field_mapping:
            # Explicit mapping with fan-out support
            rows = flatten_to_rows(data, field_mapping)
        else:
            # Backward compat: name-match fields to columns
            logger.warning(
                "export_node: no field_mapping configured, falling back to name-matching "
                "(deprecated — configure field_mapping for explicit control)"
            )
            col_names = {col["name"] for col in store.schema_definition}
            row_data = {k: v for k, v in data.items() if k in col_names}
            rows = [row_data] if row_data else []

        if not rows:
            return {
                **state,
                "exported": True,
                "rows_exported": 0,
                "current_step": "done",
            }

        source_metadata = {
            "source": "pipeline",
            "run_id": str(state.get("run_id", "")),
            "document_id": str(state.get("document_id", "")),
            "extraction_result_id": str(state.get("extraction_result_id", "")),
        }

        count = await repo.bulk_insert(
            store.table_name, store.schema_definition, rows, source_metadata=source_metadata
        )
        new_count = await repo.count_rows(store.table_name)
        await repo.update_row_count(store.id, new_count)

    return {
        **state,
        "exported": True,
        "rows_exported": count,
        "current_step": "done",
    }


async def parse_node(state: dict, *, node_config: dict | None = None) -> dict:
    """Parse a source document into a ParsedDocument, then merge results into state.

    Opens its own session (like export_node) because the agents engine runs the
    graph inline within the request. Resolves BYOK keys from state["user_id"];
    keys are never read from or written to state.
    """
    from uuid import UUID

    from app.database import AsyncSessionLocal
    from app.services.agent import parsing_bridge as pb

    logger.info("parse_node: parsing source_document %s", state.get("source_document_id"))

    parse_config = dict(state.get("parse_config") or {})
    parser_type = parse_config.get("parser", "simple")

    async with AsyncSessionLocal() as session:
        source, file_path = await pb.resolve_source_cdm(
            session, UUID(str(state["source_document_id"]))
        )
        service = await pb.build_parsing_service(
            session, UUID(str(state["user_id"])), parser_type
        )
        outcome = await pb.run_parse(
            session, service, source,
            file_path=file_path,
            representation_kind=state["representation_kind"],
            config=parse_config,
            project_id=state["project_id"],
        )

    return {**state, **outcome.as_state(), "current_step": "parsed"}
