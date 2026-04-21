"""Eval harness fixtures — loads recorded LlamaParse JSON responses."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterator, Tuple

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _fixture_cases() -> Iterator[Tuple[str, Path]]:
    for path in sorted(FIXTURES_DIR.glob("*.json")):
        if path.name.endswith(".expected.json"):
            continue
        yield path.stem, path


@pytest.fixture(params=list(_fixture_cases()), ids=lambda c: c[0])
def llamaparse_fixture(request) -> Tuple[str, Dict]:
    name, path = request.param
    with path.open("r", encoding="utf-8") as f:
        return name, json.load(f)
