"""Service for experiment management."""
import logging
from uuid import UUID

from app.models.experiment import ExperimentStatus
from app.repositories.experiment_repository import ExperimentRepository
from app.schemas.experiment import (
    ExperimentCreate,
    ExperimentUpdate,
    ExperimentResponse,
    ExperimentDetailResponse,
    VariableDiff,
)
from app.schemas.eval_run import EvalRunResponse, ModelConfig
from app.services.exceptions import NotFoundError

logger = logging.getLogger(__name__)


class ExperimentService:
    def __init__(self, experiment_repo: ExperimentRepository):
        self.repo = experiment_repo

    async def create(
        self, project_id: UUID, user_id: UUID, data: ExperimentCreate
    ) -> ExperimentResponse:
        experiment = await self.repo.create(
            project_id=project_id,
            name=data.name,
            user_id=user_id,
            description=data.description,
        )
        return self._to_response(experiment)

    async def list_by_project(self, project_id: UUID) -> list[ExperimentResponse]:
        experiments = await self.repo.list_by_project(project_id)
        result = []
        for exp in experiments:
            run_count = await self.repo.get_run_count(exp.id)
            resp = self._to_response(exp, run_count=run_count)
            result.append(resp)
        return result

    async def get_detail(
        self, experiment_id: UUID, project_id: UUID
    ) -> ExperimentDetailResponse:
        experiment = await self.repo.get_by_id(experiment_id, project_id)
        if not experiment:
            raise NotFoundError(f"Experiment {experiment_id} not found")

        runs = experiment.runs or []
        run_responses = [self._run_to_response(r) for r in runs]
        # Sort by created_at desc
        run_responses.sort(key=lambda r: r.created_at, reverse=True)

        variable_diff = self._compute_variable_diff(runs)

        baseline_run_resp = None
        if experiment.baseline_run:
            baseline_run_resp = self._run_to_response(experiment.baseline_run)

        return ExperimentDetailResponse(
            id=experiment.id,
            name=experiment.name,
            description=experiment.description,
            status=experiment.status.value if hasattr(experiment.status, 'value') else experiment.status,
            notes=experiment.notes,
            baseline_run_id=experiment.baseline_run_id,
            baseline_run=baseline_run_resp,
            run_count=len(runs),
            created_by=experiment.created_by,
            created_at=experiment.created_at,
            updated_at=experiment.updated_at,
            runs=run_responses,
            variable_diff=variable_diff,
        )

    async def update(
        self, experiment_id: UUID, project_id: UUID, data: ExperimentUpdate
    ) -> ExperimentResponse:
        fields = {}
        if data.name is not None:
            fields['name'] = data.name
        if data.description is not None:
            fields['description'] = data.description
        if data.notes is not None:
            fields['notes'] = data.notes
        if data.status is not None:
            fields['status'] = ExperimentStatus(data.status)
        if data.baseline_run_id is not None:
            fields['baseline_run_id'] = data.baseline_run_id

        experiment = await self.repo.update(experiment_id, project_id, **fields)
        if not experiment:
            raise NotFoundError(f"Experiment {experiment_id} not found")

        run_count = await self.repo.get_run_count(experiment.id)
        return self._to_response(experiment, run_count=run_count)

    async def delete(self, experiment_id: UUID, project_id: UUID) -> None:
        deleted = await self.repo.delete(experiment_id, project_id)
        if not deleted:
            raise NotFoundError(f"Experiment {experiment_id} not found")

    def _compute_variable_diff(self, runs) -> VariableDiff:
        """Compare config across runs to find what varies and what's constant."""
        if len(runs) < 2:
            return VariableDiff()

        fields_to_compare = {
            'index': lambda r: r.index.name if r.index else str(r.index_id),
            'searchType': lambda r: r.config.get('searchType', 'semantic') if r.config else 'semantic',
            'topK': lambda r: str(r.config.get('topK', 5)) if r.config else '5',
            'similarityThreshold': lambda r: str(r.config.get('similarityThreshold', 0)) if r.config else '0',
            'mode': lambda r: r.mode,
            'generationModel': lambda r: f"{r.generation_model_provider}:{r.generation_model_id}" if r.generation_model_provider else '—',
            'judgeModel': lambda r: f"{r.judge_model_provider}:{r.judge_model_id}" if r.judge_model_provider else '—',
            'systemPrompt': lambda r: ((r.llm_config or {}).get('system_prompt') or '(default)')[:80],
        }

        varying = {}
        constant = {}

        for field_name, extractor in fields_to_compare.items():
            values = []
            for run in runs:
                try:
                    values.append(extractor(run))
                except Exception:
                    values.append('—')

            unique_values = set(values)
            if len(unique_values) > 1:
                varying[field_name] = values
            else:
                constant[field_name] = values[0] if values else '—'

        return VariableDiff(varying=varying, constant=constant)

    @staticmethod
    def _run_to_response(run) -> EvalRunResponse:
        gs_name = run.golden_set.name if run.golden_set else ""
        idx_name = run.index.name if run.index else ""

        gen_model = None
        if run.generation_model_provider and run.generation_model_id:
            gen_model = ModelConfig(
                provider=run.generation_model_provider,
                model_id=run.generation_model_id,
            )

        judge_model = None
        if run.judge_model_provider and run.judge_model_id:
            judge_model = ModelConfig(
                provider=run.judge_model_provider,
                model_id=run.judge_model_id,
            )

        exp_name = None
        if run.experiment:
            exp_name = run.experiment.name

        return EvalRunResponse(
            id=run.id,
            name=run.name,
            golden_set_id=run.golden_set_id,
            golden_set_name=gs_name,
            index_id=run.index_id,
            index_name=idx_name,
            config=run.config,
            status=run.status.value if hasattr(run.status, 'value') else run.status,
            metrics=run.metrics,
            error_message=run.error_message,
            created_by=run.created_by,
            created_at=run.created_at,
            mode=run.mode,
            generation_model=gen_model,
            judge_model=judge_model,
            items_completed=run.items_completed,
            failed_item_count=run.failed_item_count,
            experiment_id=run.experiment_id,
            experiment_name=exp_name,
            variant_label=run.variant_label,
            llm_config=run.llm_config,
        )

    def _to_response(self, experiment, run_count: int = 0) -> ExperimentResponse:
        baseline_run_resp = None
        if experiment.baseline_run:
            baseline_run_resp = self._run_to_response(experiment.baseline_run)

        return ExperimentResponse(
            id=experiment.id,
            name=experiment.name,
            description=experiment.description,
            status=experiment.status.value if hasattr(experiment.status, 'value') else experiment.status,
            notes=experiment.notes,
            baseline_run_id=experiment.baseline_run_id,
            baseline_run=baseline_run_resp,
            run_count=run_count,
            created_by=experiment.created_by,
            created_at=experiment.created_at,
            updated_at=experiment.updated_at,
        )
