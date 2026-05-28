from __future__ import annotations
import logging
import time
from uuid import UUID

from app.cdm.models import ParsedDocument
from app.services.classification.port import ClassificationPort

logger = logging.getLogger(__name__)


class ClassificationService:
    def __init__(self, repo: object, classifier: ClassificationPort) -> None:
        self.repo = repo
        self.classifier = classifier

    async def execute(
        self,
        run_id: UUID,
        doc: ParsedDocument,
        labels: list[str],
    ) -> None:
        await self.repo.update_status(run_id=run_id, status="running")
        start = time.monotonic()

        try:
            result = await self.classifier.classify(doc, labels)
            await self.repo.save_regions(run_id=run_id, regions=result.regions)
            duration_ms = int((time.monotonic() - start) * 1000)
            await self.repo.update_completed(
                run_id=run_id,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            logger.exception("Classification run %s failed", run_id)
            await self.repo.update_status(run_id=run_id, status="failed", error=str(exc))
            raise
