"""Port + DTOs for ExtractionResult transforms. Primitives are pure functions over rows."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class TransformInput:
    rows: list[dict]
    source_result_id: str | None = None


@dataclass
class TransformResult:
    rows: list[dict]
    flags: list[dict] = field(default_factory=list)


@runtime_checkable
class ExtractionResultTransform(Protocol):
    @property
    def transform_type(self) -> str: ...

    def apply(self, inputs: list[TransformInput], config: dict[str, Any]) -> TransformResult: ...
