"""Deterministic identity for a Variant = (adapter, config)."""
from __future__ import annotations

import hashlib
import json


def variant_key(adapter: str, config: dict | None) -> str:
    normalized = json.dumps(config or {}, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    return f"{adapter}@{digest}"
