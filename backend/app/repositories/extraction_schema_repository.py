"""Repository for extraction schema data access."""
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction_schema import ExtractionSchema
from app.models.project import Project


class ExtractionSchemaRepository:
    """Repository for extraction schema data access."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        project_id: UUID,
        name: str,
        schema_definition: dict,
        created_by: UUID,
        description: str | None = None,
        extraction_target: str = "PER_DOC",
    ) -> ExtractionSchema:
        """Create a new extraction schema."""
        schema = ExtractionSchema(
            project_id=project_id,
            name=name,
            description=description,
            schema_definition=schema_definition,
            extraction_target=extraction_target,
            created_by=created_by,
        )
        self.session.add(schema)
        await self.session.commit()
        await self.session.refresh(schema)
        return schema

    async def get_by_id(self, schema_id: UUID) -> ExtractionSchema | None:
        """Get an extraction schema by ID (unscoped)."""
        result = await self.session.execute(
            select(ExtractionSchema).where(ExtractionSchema.id == schema_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_for_user(
        self, schema_id: UUID, user_id: UUID
    ) -> ExtractionSchema | None:
        """Get an extraction schema by ID, scoped to user's projects."""
        result = await self.session.execute(
            select(ExtractionSchema)
            .join(ExtractionSchema.project)
            .where(and_(
                ExtractionSchema.id == schema_id,
                Project.user_id == user_id,
            ))
        )
        return result.scalar_one_or_none()

    async def list_by_project(
        self, project_id: UUID, user_id: UUID
    ) -> list[ExtractionSchema]:
        """List all extraction schemas for a project."""
        result = await self.session.execute(
            select(ExtractionSchema)
            .join(ExtractionSchema.project)
            .where(and_(
                ExtractionSchema.project_id == project_id,
                Project.user_id == user_id,
            ))
            .order_by(ExtractionSchema.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(
        self,
        schema_id: UUID,
        user_id: UUID,
        name: str | None = None,
        description: str | None = None,
        schema_definition: dict | None = None,
        extraction_target: str | None = None,
    ) -> ExtractionSchema | None:
        """Update an extraction schema."""
        schema = await self.get_by_id_for_user(schema_id, user_id)
        if not schema:
            return None

        if name is not None:
            schema.name = name
        if description is not None:
            schema.description = description
        if schema_definition is not None:
            schema.schema_definition = schema_definition
        if extraction_target is not None:
            schema.extraction_target = extraction_target

        await self.session.commit()
        await self.session.refresh(schema)
        return schema

    async def delete(self, schema_id: UUID, user_id: UUID) -> bool:
        """Delete an extraction schema."""
        schema = await self.get_by_id_for_user(schema_id, user_id)
        if not schema:
            return False
        await self.session.delete(schema)
        await self.session.commit()
        return True
