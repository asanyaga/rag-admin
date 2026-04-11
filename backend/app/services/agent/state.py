"""State type for agent graph execution."""

# Plain dict so LangGraph preserves all keys.
# TypedDict(total=False) drops undeclared keys, so we use dict instead.
AgentState = dict
