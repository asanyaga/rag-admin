"""Append-only JSONL metrics log for eval runs."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

LOG_PATH = Path(__file__).parent / "metrics.jsonl"


def record(entry: Dict[str, Any]) -> None:
    entry_with_ts = {"ts": datetime.now(timezone.utc).isoformat(), **entry}
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry_with_ts) + "\n")
