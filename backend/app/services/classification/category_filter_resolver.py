"""Resolve category_filter preprocess stages into concrete keep-sets.

Runs at extraction request time (router layer) so misconfiguration fails fast
with HTTP 400/404 before any LLM tokens are spent. Keeps the preprocess stage
itself a pure function.
"""
from __future__ import annotations

from uuid import UUID

from app.repositories.classification_run_repository import ClassificationRunRepository
from app.services.exceptions import NotFoundError


async def resolve_category_filter_stages(
    preprocess: list[dict] | None,
    parse_run_id: UUID,
    repo: ClassificationRunRepository,
) -> tuple[list[dict], dict | None]:
    if not preprocess:
        return preprocess or [], None

    resolved: list[dict] = []
    summary: dict | None = None

    for stage in preprocess:
        if stage.get("stage") != "category_filter":
            resolved.append(stage)
            continue

        cfg = dict(stage.get("config") or {})
        run_id_raw = cfg.get("classificationRunId")
        if not run_id_raw:
            raise ValueError("category_filter requires classificationRunId")
        categories = cfg.get("categories") or []
        if not categories:
            raise ValueError("category_filter requires at least one category")
        granularity = cfg.get("granularity") or "page"
        if granularity not in ("page", "block"):
            raise ValueError(f"Invalid category_filter granularity: {granularity!r}")

        run_id = UUID(str(run_id_raw))
        run = await repo.get(run_id)
        if run is None:
            raise NotFoundError(f"Classification run {run_id} not found")
        if run.status != "completed":
            raise ValueError(
                f"Classification run {run_id} is not completed (status={run.status})"
            )
        if str(run.parse_run_id) != str(parse_run_id):
            raise ValueError(
                "Classification run was produced from a different parse; "
                "its page/block IDs would not align with this extraction"
            )

        wanted = set(categories)
        selected = [r for r in await repo.get_regions(run_id) if r.label in wanted]

        keep_pages: set[int] = set()
        keep_block_ids: set[str] = set()
        if granularity == "page":
            for r in selected:
                keep_pages.update(range(r.page_start, r.page_end + 1))
        else:
            for r in selected:
                if r.block_ids:
                    keep_block_ids.update(str(b) for b in r.block_ids)
                else:
                    keep_pages.update(range(r.page_start, r.page_end + 1))

        if not keep_pages and not keep_block_ids:
            raise ValueError(
                f"Selected categories matched no content in classification run {run_id}"
            )

        cfg["keepPages"] = sorted(keep_pages)
        cfg["keepBlockIds"] = sorted(keep_block_ids)
        resolved.append({"stage": "category_filter", "config": cfg})
        summary = {
            "classificationRunId": str(run_id),
            "categories": list(categories),
            "granularity": granularity,
            "keptPages": len(keep_pages),
            "keptBlocks": len(keep_block_ids),
        }

    return resolved, summary
