"""telemetry.py - observability and tracing.

traces tasks from prompt to commit. tracks cost, time, tokens,
error rates. exports spans in a format compatible with COEF and
opentelemetry-like systems.

in the world: the scribe of fire. every flame leaves a trace.
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from keanu.paths import keanu_home


_SPANS_LOG = keanu_home() / "spans.jsonl"
_ACTIVE_SPANS: dict[str, "Span"] = {}
_SPAN_COUNTER = 0


@dataclass
class Span:
    """a trace span representing an operation."""
    name: str
    trace_id: str = ""
    span_id: str = ""
    parent_id: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    status: str = "ok"  # ok, error
    attributes: dict = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)

    def __post_init__(self):
        global _SPAN_COUNTER
        _SPAN_COUNTER += 1
        if not self.span_id:
            self.span_id = f"s_{int(time.time() * 1000) % 1_000_000_000}_{_SPAN_COUNTER}"
        if not self.trace_id:
            self.trace_id = f"t_{int(time.time() * 1000) % 1_000_000_000}_{_SPAN_COUNTER}"
        if not self.start_time:
            self.start_time = time.time()

    @property
    def duration_ms(self) -> int:
        if self.end_time:
            return int((self.end_time - self.start_time) * 1000)
        return int((time.time() - self.start_time) * 1000)

    def add_event(self, name: str, **attrs):
        """add a timestamped event to the span."""
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            **attrs,
        })

    def set_error(self, error: str):
        """mark the span as errored."""
        self.status = "error"
        self.attributes["error"] = error

    def end(self):
        """end the span."""
        self.end_time = time.time()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events,
        }


# ============================================================
# SPAN MANAGEMENT
# ============================================================

def start_span(name: str, trace_id: str = "", parent_id: str = "",
               **attributes) -> Span:
    """start a new span."""
    span = Span(
        name=name,
        trace_id=trace_id,
        parent_id=parent_id,
        attributes=attributes,
    )
    _ACTIVE_SPANS[span.span_id] = span
    return span


def end_span(span: Span):
    """end a span and persist it."""
    span.end()
    _ACTIVE_SPANS.pop(span.span_id, None)
    _persist_span(span)


def get_active_spans() -> list[Span]:
    """get all currently active spans."""
    return list(_ACTIVE_SPANS.values())


class trace_span:
    """context manager for tracing a block of code."""

    def __init__(self, name: str, trace_id: str = "", parent_id: str = "",
                 **attributes):
        self.name = name
        self.trace_id = trace_id
        self.parent_id = parent_id
        self.attributes = attributes
        self.span: Span | None = None

    def __enter__(self) -> Span:
        self.span = start_span(
            self.name,
            trace_id=self.trace_id,
            parent_id=self.parent_id,
            **self.attributes,
        )
        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.span:
            if exc_type:
                self.span.set_error(str(exc_val))
            end_span(self.span)
        return False  # don't suppress exceptions


# ============================================================
# PERSISTENCE
# ============================================================

def _persist_span(span: Span):
    """write a span to the log file."""
    _SPANS_LOG.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(_SPANS_LOG, "a") as f:
            f.write(json.dumps(span.to_dict()) + "\n")
    except OSError:
        pass


def get_spans(limit: int = 100, trace_id: str = "") -> list[dict]:
    """read recent spans from the log."""
    if not _SPANS_LOG.exists():
        return []
    entries = []
    try:
        for line in _SPANS_LOG.read_text().strip().split("\n"):
            if line.strip():
                entry = json.loads(line)
                if trace_id and entry.get("trace_id") != trace_id:
                    continue
                entries.append(entry)
    except (json.JSONDecodeError, OSError):
        pass
    return entries[-limit:]


# ============================================================
# TRACE ANALYSIS
# ============================================================

@dataclass
class TraceStats:
    """statistics about traced operations."""
    total_spans: int = 0
    total_traces: int = 0
    avg_duration_ms: float = 0.0
    error_rate: float = 0.0
    by_name: dict = field(default_factory=dict)
    total_tokens: int = 0
    total_cost: float = 0.0


def analyze_traces(spans: list[dict] | None = None) -> TraceStats:
    """analyze trace data for statistics."""
    if spans is None:
        spans = get_spans(limit=500)

    if not spans:
        return TraceStats()

    stats = TraceStats(total_spans=len(spans))

    traces = set()
    errors = 0
    total_duration = 0
    name_counts: dict[str, dict] = {}

    for span in spans:
        traces.add(span.get("trace_id", ""))
        if span.get("status") == "error":
            errors += 1
        duration = span.get("duration_ms", 0)
        total_duration += duration

        name = span.get("name", "unknown")
        if name not in name_counts:
            name_counts[name] = {"count": 0, "total_ms": 0, "errors": 0}
        name_counts[name]["count"] += 1
        name_counts[name]["total_ms"] += duration
        if span.get("status") == "error":
            name_counts[name]["errors"] += 1

        attrs = span.get("attributes", {})
        stats.total_tokens += attrs.get("tokens", 0)
        stats.total_cost += attrs.get("cost", 0.0)

    stats.total_traces = len(traces)
    stats.avg_duration_ms = total_duration / len(spans) if spans else 0
    stats.error_rate = errors / len(spans) if spans else 0

    stats.by_name = {
        name: {
            "count": data["count"],
            "avg_ms": data["total_ms"] / data["count"] if data["count"] else 0,
            "error_rate": data["errors"] / data["count"] if data["count"] else 0,
        }
        for name, data in sorted(name_counts.items(), key=lambda x: -x[1]["count"])
    }

    return stats


def trace_summary(days: int = 7) -> dict:
    """summarize trace data for the last N days."""
    cutoff = time.time() - (days * 86400)
    all_spans = get_spans(limit=5000)
    recent = [s for s in all_spans if s.get("start_time", 0) >= cutoff]

    stats = analyze_traces(recent)

    return {
        "period_days": days,
        "total_spans": stats.total_spans,
        "total_traces": stats.total_traces,
        "avg_duration_ms": round(stats.avg_duration_ms, 1),
        "error_rate": round(stats.error_rate, 3),
        "total_tokens": stats.total_tokens,
        "total_cost": round(stats.total_cost, 4),
        "by_name": stats.by_name,
    }
