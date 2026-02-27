"""Repository for experiment data access."""
from uuid import UUID
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.experiment import Experiment
from app.models.eval_run import EvalRun


class ExperimentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        project_id: UUID,
        name: str,
        user_id: UUID,
        description: str | None = None,
    ) -> Experiment:
        experiment = Experiment(
            project_id=project_id,
            name=name,
            description=description,
            created_by=user_id,
        )
        self.session.add(experiment)
        await self.session.commit()
        await self.session.refresh(experiment)
        return experiment

    async def get_by_id(
        self, experiment_id: UUID, project_id: UUID
    ) -> Experiment | None:
        result = await self.session.execute(
            select(Experiment)
            .options(
                selectinload(Experiment.baseline_run),
                selectinload(Experiment.runs)
                .selectinload(EvalRun.golden_set),
                selectinload(Experiment.runs)
                .selectinload(EvalRun.index),
            )
            .where(
                Experiment.id == experiment_id,
                Experiment.project_id == project_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_project(self, project_id: UUID) -> list[Experiment]:
        result = await self.session.execute(
            select(Experiment)
            .options(selectinload(Experiment.baseline_run))
            .where(Experiment.project_id == project_id)
            .order_by(Experiment.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(
        self,
        experiment_id: UUID,
        project_id: UUID,
        **fields,
    ) -> Experiment | None:
        result = await self.session.execute(
            select(Experiment).where(
                Experiment.id == experiment_id,
                Experiment.project_id == project_id,
            )
        )
        experiment = result.scalar_one_or_none()
        if not experiment:
            return None

        for key, value in fields.items():
            if hasattr(experiment, key):
                setattr(experiment, key, value)

        await self.session.commit()
        await self.session.refresh(experiment)
        return experiment

    async def delete(self, experiment_id: UUID, project_id: UUID) -> bool:
        # First unlink all runs from this experiment
        runs_result = await self.session.execute(
            select(EvalRun).where(EvalRun.experiment_id == experiment_id)
        )
        for run in runs_result.scalars().all():
            run.experiment_id = None
            run.variant_label = None

        result = await self.session.execute(
            delete(Experiment).where(
                Experiment.id == experiment_id,
                Experiment.project_id == project_id,
            )
        )
        await self.session.commit()
        return result.rowcount > 0

    async def get_run_count(self, experiment_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count()).where(EvalRun.experiment_id == experiment_id)
        )
        return result.scalar() or 0
