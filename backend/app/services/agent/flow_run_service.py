"""Flow run service — generic execution engine for composed flows."""
import json
import logging
from uuid import UUID, uuid4

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command

from app.models.flow_run import FlowRunStatus
from app.repositories.flow_definition_repository import FlowDefinitionRepository
from app.repositories.flow_run_repository import FlowRunRepository
from app.schemas.agent import FlowRunResponse, FlowRunListItem
from app.services.agent.graph import build_graph_from_definition
from app.services.agent.state import GenericFlowState
from app.services.exceptions import NotFoundError

logger = logging.getLogger(__name__)


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


class FlowRunService:
    """Service for executing flow definitions through the LangGraph engine."""

    def __init__(
        self,
        flow_run_repo: FlowRunRepository,
        flow_def_repo: FlowDefinitionRepository,
        checkpointer: AsyncPostgresSaver,
    ):
        self.flow_run_repo = flow_run_repo
        self.flow_def_repo = flow_def_repo
        self.checkpointer = checkpointer

    async def start_run(
        self,
        project_id: UUID,
        flow_definition_id: UUID,
        initial_state: dict,
        user_id: UUID,
    ) -> FlowRunResponse:
        """Start executing a flow definition with the given initial state."""
        # Validate flow definition exists
        flow_def = await self.flow_def_repo.get_by_id(flow_definition_id)
        if not flow_def:
            raise NotFoundError(f"Flow definition {flow_definition_id} not found")

        # Create run record
        run = await self.flow_run_repo.create(
            project_id=project_id,
            flow_definition_id=flow_definition_id,
            created_by=user_id,
            initial_state=initial_state,
        )

        # Update status to running
        await self.flow_run_repo.update_status(run.id, FlowRunStatus.running)

        # Build and invoke graph
        thread_id = str(uuid4())
        compiled = build_graph_from_definition(
            flow=flow_def.definition,
            checkpointer=self.checkpointer,
            state_type=GenericFlowState,
        )
        config = {"configurable": {"thread_id": thread_id}}

        try:
            result = await compiled.ainvoke(initial_state, config=config)

            if result.get("error"):
                await self.flow_run_repo.update_state(
                    run.id,
                    current_state=_make_json_safe(result),
                    current_node=result.get("current_step"),
                    status=FlowRunStatus.failed,
                    thread_id=thread_id,
                    status_message=result.get("error"),
                )
            else:
                # Check if graph completed or interrupted
                snapshot = await compiled.aget_state(config)
                if snapshot.next:
                    # Interrupted — waiting for human input
                    await self.flow_run_repo.update_state(
                        run.id,
                        current_state=_make_json_safe(result),
                        current_node=snapshot.next[0] if snapshot.next else None,
                        status=FlowRunStatus.waiting_for_input,
                        thread_id=thread_id,
                    )
                else:
                    # Completed
                    await self.flow_run_repo.update_state(
                        run.id,
                        current_state=_make_json_safe(result),
                        current_node=None,
                        status=FlowRunStatus.completed,
                        thread_id=thread_id,
                    )

        except Exception as e:
            logger.exception("Flow run failed for run %s", run.id)
            await self.flow_run_repo.update_status(
                run.id, FlowRunStatus.failed, str(e)
            )

        run = await self.flow_run_repo.get_by_id(run.id)
        return FlowRunResponse.from_orm_model(run)

    async def get_run(self, run_id: UUID) -> FlowRunResponse:
        """Get a flow run by ID."""
        run = await self.flow_run_repo.get_by_id(run_id)
        if not run:
            raise NotFoundError(f"Flow run {run_id} not found")
        return FlowRunResponse.from_orm_model(run)

    async def list_runs(self, project_id: UUID) -> list[FlowRunListItem]:
        """List flow runs for a project."""
        runs = await self.flow_run_repo.list_by_project(project_id)
        return [FlowRunListItem.from_orm_model(r) for r in runs]

    async def resume_run(
        self,
        run_id: UUID,
        resume_value: dict,
    ) -> FlowRunResponse:
        """Resume an interrupted flow run with the given value."""
        run = await self.flow_run_repo.get_by_id(run_id)
        if not run:
            raise NotFoundError(f"Flow run {run_id} not found")

        if run.status != FlowRunStatus.waiting_for_input:
            raise ValueError(f"Flow run {run_id} is not waiting for input")

        if not run.thread_id:
            raise ValueError(f"Flow run {run_id} has no thread_id")

        # Load flow definition to rebuild graph
        flow_def = await self.flow_def_repo.get_by_id(run.flow_definition_id)
        if not flow_def:
            raise NotFoundError(f"Flow definition {run.flow_definition_id} not found")

        compiled = build_graph_from_definition(
            flow=flow_def.definition,
            checkpointer=self.checkpointer,
            state_type=GenericFlowState,
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
                await self.flow_run_repo.update_state(
                    run.id,
                    current_state=_make_json_safe(result),
                    current_node=snapshot.next[0] if snapshot.next else None,
                    status=FlowRunStatus.waiting_for_input,
                )
            else:
                await self.flow_run_repo.update_state(
                    run.id,
                    current_state=_make_json_safe(result),
                    current_node=None,
                    status=FlowRunStatus.completed,
                )

        except Exception as e:
            logger.exception("Resume failed for flow run %s", run.id)
            await self.flow_run_repo.update_status(
                run.id, FlowRunStatus.failed, str(e)
            )

        run = await self.flow_run_repo.get_by_id(run.id)
        return FlowRunResponse.from_orm_model(run)
