"""Agent tool registry — reusable building blocks for composing agent graphs."""
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolDefinition:
    """A reusable tool that can be wired into an agent graph.

    Each tool declares what state keys it reads (input_keys) and writes
    (output_keys), plus an optional JSON Schema for per-instance configuration.
    """

    slug: str
    name: str
    category: str  # "extraction", "control", "export", "indexing", "trigger"
    description: str
    input_keys: list[str]
    output_keys: list[str]
    node_fn: Callable
    config_schema: dict[str, Any] = field(default_factory=dict)


_registry: dict[str, ToolDefinition] = {}


def register_tool(definition: ToolDefinition) -> None:
    """Register a tool in the global registry."""
    _registry[definition.slug] = definition


def get_tool(slug: str) -> ToolDefinition | None:
    """Get a tool by slug."""
    return _registry.get(slug)


def list_tools() -> list[ToolDefinition]:
    """List all registered tools."""
    return list(_registry.values())
