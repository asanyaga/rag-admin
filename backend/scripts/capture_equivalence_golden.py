"""Run ONCE on the pre-refactor branch to snapshot current pipeline output.

    cd backend && uv run python scripts/capture_equivalence_golden.py

Writes tests/.../fixtures/equivalence/<name>.json. Commit the results; Task A5's
test compares the post-refactor pipeline against them.
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.cdm.source import SourceDocument
from app.services.parsing.custom_pipeline_runner import run_custom_pipeline
from tests.cdm.adapters.custom_pipeline.fixtures.equivalence_fixtures import (
    EQUIV_CONFIGS, build_for, content_projection,
)

GOLDEN_DIR = (Path(__file__).resolve().parents[1]
              / "tests/cdm/adapters/custom_pipeline/fixtures/equivalence")


def _source() -> SourceDocument:
    return SourceDocument(
        id="src-1", sha256="b" * 64, filename="equiv.pdf",
        mime_type="application/pdf", byte_size=1234,
        created_at=datetime.now(timezone.utc),
    )


async def main() -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for name, config in EQUIV_CONFIGS.items():
        pdf = GOLDEN_DIR / f"{name}.pdf"
        build_for(name, pdf)
        _, parsed = await run_custom_pipeline(
            source=_source(), file_path=str(pdf),
            representation_kind="extract_rich", config=config, client=None)
        (GOLDEN_DIR / f"{name}.json").write_text(
            json.dumps(content_projection(parsed), indent=2, sort_keys=True))
        pdf.unlink(missing_ok=True)
        print(f"captured {name}")


if __name__ == "__main__":
    asyncio.run(main())
