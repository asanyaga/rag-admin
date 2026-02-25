"""TraceCollector — builds a QueryTrace during pipeline execution."""

import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator

from app.services.tracing import QueryTrace, Span, SpanMetrics


class TraceCollector:
    """Collects spans during a query execution. One instance per query."""

    def __init__(self, query: str, search_type: str):
        self._trace_id = str(uuid.uuid4())
        self._query = query
        self._search_type = search_type
        self._spans: list[Span] = []
        self._order_counter = 0
        self._start = time.perf_counter()

    @contextmanager
    def span(
        self,
        span_type: str,
        name: str,
        input: Any = None,
        parent_id: str | None = None,
    ) -> Generator[Span, None, None]:
        """Context manager that auto-captures timing for a pipeline step."""
        span_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc).isoformat()
        self._order_counter += 1

        s = Span(
            id=span_id,
            parent_id=parent_id,
            span_type=span_type,
            name=name,
            input=input,
            started_at=started_at,
            order=self._order_counter,
        )

        t0 = time.perf_counter()
        try:
            yield s
        except Exception as exc:
            s.status = "error"
            s.error = str(exc)
            raise
        finally:
            elapsed = (time.perf_counter() - t0) * 1000
            s.ended_at = datetime.now(timezone.utc).isoformat()
            s.duration_ms = round(elapsed, 2)
            if s.metrics.latency_ms is None:
                s.metrics.latency_ms = round(elapsed, 2)
            self._spans.append(s)

    def add_child(self, parent: Span, child: Span) -> None:
        """Attach a child span to a parent for nested display."""
        parent.children.append(child)

    def build_trace(self) -> QueryTrace:
        """Finalize and return the complete trace."""
        total_ms = (time.perf_counter() - self._start) * 1000
        # Build tree: top-level spans only (children are attached inline)
        top_level = [s for s in self._spans if s.parent_id is None]
        return QueryTrace(
            trace_id=self._trace_id,
            query=self._query,
            search_type=self._search_type,
            total_duration_ms=round(total_ms, 2),
            spans=top_level,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
