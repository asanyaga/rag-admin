"""Agent type registry — discovers and provides available agent types."""
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class AgentTypeDefinition:
    """Metadata for a registered agent type."""
    slug: str
    name: str
    description: str
    nodes: list[dict[str, str]]  # [{"name": "extract", "label": "Extract Data"}, ...]
    graph_builder: Callable  # (checkpointer) -> compiled graph
    config_schema: dict[str, Any] = field(default_factory=dict)
    flow_definition: dict[str, Any] | None = None  # composable flow definition


_registry: dict[str, AgentTypeDefinition] = {}


def register_agent_type(definition: AgentTypeDefinition) -> None:
    """Register an agent type in the global registry."""
    _registry[definition.slug] = definition


def get_agent_type(slug: str) -> AgentTypeDefinition | None:
    """Get an agent type by slug."""
    _ensure_loaded()
    return _registry.get(slug)


def list_agent_types() -> list[AgentTypeDefinition]:
    """List all registered agent types."""
    _ensure_loaded()
    return list(_registry.values())


_loaded = False


def _ensure_loaded() -> None:
    """Lazy-load agent type modules on first access."""
    global _loaded
    if _loaded:
        return
    _loaded = True
    # Import type modules to trigger registration
    from app.services.agent.types import receipt_processing  # noqa: F401
