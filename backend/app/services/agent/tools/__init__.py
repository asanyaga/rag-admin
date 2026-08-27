"""Agent tool registry — reusable building blocks for composing agent graphs."""
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class FieldSpec:
    """A runtime input a tool needs, and how the run form should render it."""
    key: str
    label: str
    widget: str  # e.g. "source_document_picker", "parsed_document_picker"


@dataclass
class ToolDefinition:
    """A reusable tool wired into an agent graph.

    Three channels, kept distinct:
      - config_schema: design-time knobs, bound per-node into the graph.
      - runtime_inputs: data supplied at run-time OR by an upstream node's output.
      - outputs: keys this node writes into state.
    """
    slug: str
    name: str
    category: str
    description: str
    node_fn: Callable
    runtime_inputs: list[FieldSpec] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    config_schema: dict[str, Any] = field(default_factory=dict)
    config_panel: str | None = None


_registry: dict[str, ToolDefinition] = {}


def register_tool(definition: ToolDefinition) -> None:
    """Register a tool in the global registry."""
    _registry[definition.slug] = definition


def get_tool(slug: str) -> ToolDefinition | None:
    """Get a tool by slug."""
    _ensure_loaded()
    return _registry.get(slug)


def list_tools() -> list[ToolDefinition]:
    """List all registered tools."""
    _ensure_loaded()
    return list(_registry.values())


_loaded = False


def _ensure_loaded() -> None:
    """Lazy-load tool modules on first access."""
    global _loaded
    if _loaded:
        return
    _loaded = True
    from app.services.agent.tools import extract  # noqa: F401
    from app.services.agent.tools import review  # noqa: F401
    from app.services.agent.tools import export  # noqa: F401
    from app.services.agent.tools import parse  # noqa: F401
