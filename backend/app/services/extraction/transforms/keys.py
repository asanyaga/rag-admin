"""Pure key-normalization for grouping rows in transforms."""
from __future__ import annotations

import re
from typing import Any


def normalize_key(value: Any, config: dict) -> str:
    if value is None:
        return ""
    text = str(value)
    for pat in config.get("stripPatterns", []):
        text = re.sub(pat, "", text)
    if config.get("trim", True):
        text = text.strip()
    if config.get("collapseWhitespace", True):
        text = re.sub(r"\s+", " ", text)
    if config.get("firstTokenOnly", False):
        text = text.split(" ")[0] if text else text
    letters = config.get("stripTrailingLetters", [])
    if letters:
        charset = "".join(letters)
        text = re.sub(rf"[{re.escape(charset)}]+$", "", text)
    if config.get("casefold", True):
        text = text.casefold()
    return text
