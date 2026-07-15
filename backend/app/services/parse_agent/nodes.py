"""Parse-agent graph nodes and their static contracts.

Nodes return PARTIAL deltas (only the keys they own). The graph uses a TypedDict
state schema (see graph.py) so LangGraph gives each key its own channel and the
deltas merge per-key across nodes.
"""
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class NodeSpec:
    slug: str
    input_keys: list[str]
    output_keys: list[str]


PARSE_SPEC = NodeSpec(
    slug="parse",
    input_keys=["file_path", "config", "representation_kind", "project_id", "source_document_id"],
    output_keys=["parse_run_id", "page_count", "text_len", "failed_page_count", "block_count"],
)
HEALTH_SPEC = NodeSpec(
    slug="health_check",
    input_keys=["text_len", "failed_page_count", "block_count"],
    output_keys=["quality_signal"],
)

NODE_SPECS: dict[str, NodeSpec] = {PARSE_SPEC.slug: PARSE_SPEC, HEALTH_SPEC.slug: HEALTH_SPEC}
GRAPH_NODES: list[str] = ["parse", "health_check"]


def make_parse_node(parsing_service, source):
    """Factory: returns a `parse` node closing over the parsing service + source CDM."""
    async def parse_node(state: dict) -> dict:
        run, doc = await parsing_service.parse_and_persist(
            source=source,
            file_path=state["file_path"],
            representation_kind=state["representation_kind"],
            config=state["config"],
            project_id=UUID(str(state["project_id"])),
        )
        full_text = doc.full_text or ""
        return {
            "parse_run_id": str(run.id),
            "page_count": doc.page_count,
            "text_len": len(full_text),
            "failed_page_count": len(run.failed_pages),
            "block_count": len(doc.blocks),
        }
    return parse_node


async def health_check_node(state: dict) -> dict:
    """Reference-free quality signal. Pure function of accumulated state."""
    text_len = int(state.get("text_len", 0) or 0)
    failed_pages = int(state.get("failed_page_count", 0) or 0)
    block_count = int(state.get("block_count", 0) or 0)
    return {
        "quality_signal": {
            "text_non_empty": text_len > 0,
            "failed_pages": failed_pages,
            "block_count": block_count,
            "ok": text_len > 0 and failed_pages == 0,
        }
    }
