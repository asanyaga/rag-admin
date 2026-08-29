"""Agent run service — generic execution engine for composed agents."""
import json
import logging
from uuid import UUID, uuid4

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command

from app.models.agent_run import AgentRunStatus
from app.repositories.agent_definition_repository import AgentDefinitionRepository
from app.repositories.agent_run_repository import AgentRunRepository
from app.schemas.agent import AgentRunResponse, AgentRunListItem
from app.services.agent.graph import build_agent_graph
from app.services.agent.state import AgentState
from app.services.exceptions import NotFoundError

logger = logging.getLogger(__name__)


def _with_ambient(initial_state: dict, project_id, user_id) -> dict:
    """Merge ambient identity into a copy of the initial state for invocation.

    Returns a new dict; the caller's `initial_state` (the persisted run
    record) is left unmutated.
    """
    return {
        **initial_state,
        "project_id": str(project_id),
        "user_id": str(user_id),
    }


def _make_json_safe(obj: dict) -> dict:
    """Strip non-JSON-serializable values from a state dict.

    LangGraph may embed Interrupt objects or other internal types in the
    state returned by ainvoke. We need to remove them before storing in
    a JSON column.
    """
    safe = {}
    for key, value in obj.items():
        try:
            json.dumps(value)
            safe[key] = value
        except (TypeError, ValueError):
            # Convert to string representation as fallback
            safe[key] = str(value)
    return safe


class AgentRunService:
    """Service for executing agent definitions through the LangGraph engine."""

    def __init__(
        self,
        agent_run_repo: AgentRunRepository,
        agent_def_repo: AgentDefinitionRepository,
        checkpointer: AsyncPostgresSaver,
    ):
        self.agent_run_repo = agent_run_repo
        self.agent_def_repo = agent_def_repo
        self.checkpointer = checkpointer

    async def start_run(
        self,
        project_id: UUID,
        agent_definition_id: UUID,
        initial_state: dict,
        user_id: UUID,
    ) -> AgentRunResponse:
        """Start executing an agent definition with the given initial state."""
        # Validate agent definition exists
        agent_def = await self.agent_def_repo.get_by_id(agent_definition_id)
        if not agent_def:
            raise NotFoundError(f"Agent definition {agent_definition_id} not found")

        from app.services.agent.tools import get_tool
        from app.services.agent.validation import validate_graph

        unmet = validate_graph(agent_def.definition, get_tool)
        if unmet:
            first = unmet[0]
            raise ValueError(
                f"Agent graph is not runnable: node '{first.node_id}' needs "
                f"'{first.key}' from an upstream node "
                f"({len(unmet)} unmet input(s) total)."
            )

        # Build the graph before creating the run record. build_agent_graph is a
        # pure function of the definition (e.g. it raises ValueError on an
        # unknown tool slug — a case validate_graph above does not catch, since
        # it simply skips nodes whose tool isn't registered). Building first
        # ensures such errors surface before any run row exists, so we never
        # orphan a run stuck in `running` because the graph couldn't compile.
        thread_id = str(uuid4())
        compiled = build_agent_graph(
            flow=agent_def.definition,
            checkpointer=self.checkpointer,
            state_type=AgentState,
        )

        # Create run record
        run = await self.agent_run_repo.create(
            project_id=project_id,
            agent_definition_id=agent_definition_id,
            created_by=user_id,
            initial_state=initial_state,
        )

        # Update status to running
        await self.agent_run_repo.update_status(run.id, AgentRunStatus.running)

        config = {"configurable": {"thread_id": thread_id}}
        invoke_state = _with_ambient(initial_state, project_id, user_id)

        try:
            result = await compiled.ainvoke(invoke_state, config=config)

            if result.get("error"):
                await self.agent_run_repo.update_state(
                    run.id,
                    current_state=_make_json_safe(result),
                    current_node=result.get("current_step"),
                    status=AgentRunStatus.failed,
                    thread_id=thread_id,
                    status_message=result.get("error"),
                )
            else:
                # Check if graph completed or interrupted
                snapshot = await compiled.aget_state(config)
                if snapshot.next:
                    # Interrupted — waiting for human input
                    await self.agent_run_repo.update_state(
                        run.id,
                        current_state=_make_json_safe(result),
                        current_node=snapshot.next[0] if snapshot.next else None,
                        status=AgentRunStatus.waiting_for_input,
                        thread_id=thread_id,
                    )
                else:
                    # Completed
                    await self.agent_run_repo.update_state(
                        run.id,
                        current_state=_make_json_safe(result),
                        current_node=None,
                        status=AgentRunStatus.completed,
                        thread_id=thread_id,
                    )

        except Exception as e:
            logger.exception("Agent run failed for run %s", run.id)
            await self.agent_run_repo.update_status(
                run.id, AgentRunStatus.failed, str(e)
            )

        run = await self.agent_run_repo.get_by_id(run.id)
        return AgentRunResponse.from_orm_model(run)

    async def get_run(self, run_id: UUID) -> AgentRunResponse:
        """Get an agent run by ID."""
        run = await self.agent_run_repo.get_by_id(run_id)
        if not run:
            raise NotFoundError(f"Agent run {run_id} not found")
        return AgentRunResponse.from_orm_model(run)

    async def list_runs(self, project_id: UUID) -> list[AgentRunListItem]:
        """List agent runs for a project."""
        runs = await self.agent_run_repo.list_by_project(project_id)
        return [AgentRunListItem.from_orm_model(r) for r in runs]

    async def resume_run(
        self,
        run_id: UUID,
        resume_value: dict,
    ) -> AgentRunResponse:
        """Resume an interrupted agent run with the given value."""
        run = await self.agent_run_repo.get_by_id(run_id)
        if not run:
            raise NotFoundError(f"Agent run {run_id} not found")

        if run.status != AgentRunStatus.waiting_for_input:
            raise ValueError(f"Agent run {run_id} is not waiting for input")

        if not run.thread_id:
            raise ValueError(f"Agent run {run_id} has no thread_id")

        # Load agent definition to rebuild graph
        agent_def = await self.agent_def_repo.get_by_id(run.agent_definition_id)
        if not agent_def:
            raise NotFoundError(f"Agent definition {run.agent_definition_id} not found")

        compiled = build_agent_graph(
            flow=agent_def.definition,
            checkpointer=self.checkpointer,
            state_type=AgentState,
        )
        config = {"configurable": {"thread_id": run.thread_id}}

        try:
            result = await compiled.ainvoke(
                Command(resume=resume_value),
                config=config,
            )

            # Check if graph completed or hit another interrupt
            snapshot = await compiled.aget_state(config)
            if snapshot.next:
                await self.agent_run_repo.update_state(
                    run.id,
                    current_state=_make_json_safe(result),
                    current_node=snapshot.next[0] if snapshot.next else None,
                    status=AgentRunStatus.waiting_for_input,
                )
            else:
                await self.agent_run_repo.update_state(
                    run.id,
                    current_state=_make_json_safe(result),
                    current_node=None,
                    status=AgentRunStatus.completed,
                )

        except Exception as e:
            logger.exception("Resume failed for agent run %s", run.id)
            await self.agent_run_repo.update_status(
                run.id, AgentRunStatus.failed, str(e)
            )

        run = await self.agent_run_repo.get_by_id(run.id)
        return AgentRunResponse.from_orm_model(run)
