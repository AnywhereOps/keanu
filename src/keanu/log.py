"""log.py - the backbone. logger, tracer, memory.

one level. everything visible. the log IS the memory.
remember() writes through the sink to git-backed JSONL.
recall() searches it with regex. no separate storage.

in the world: the river. everything flows through here.
what matters sticks to the banks. recall walks the banks
looking for what you left behind.
"""

import json
import re
import sys
from datetime import datetime
from contextlib import contextmanager
from pathlib import Path

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    ConsoleSpanExporter,
)

# ============================================================
# TRACER SETUP
# ============================================================

_provider = TracerProvider()
_tracer = _provider.get_tracer("keanu", "0.1.0")
_console_export = False


def enable_console_export():
    """turn on span export to stderr."""
    global _console_export
    if not _console_export:
        _provider.add_span_processor(
            SimpleSpanProcessor(ConsoleSpanExporter())
        )
        _console_export = True


def add_exporter(exporter):
    """add a custom span exporter (OTLP, Jaeger, etc)."""
    _provider.add_span_processor(SimpleSpanProcessor(exporter))


def get_tracer():
    """get the keanu tracer for custom instrumentation."""
    return _tracer


# ============================================================
# VERBOSE LOGGER - one level, everything visible
# ============================================================

_sink = None
_flush = None


def set_level(level: str):
    """no-op. kept for backwards compat. there is only verbose."""
    pass


def set_sink(fn, flush_fn=None):
    """register where logs go besides console. fn(subsystem, level, message, attrs).
    optional flush_fn is called to commit buffered entries."""
    global _sink, _flush
    _sink = fn
    _flush = flush_fn


def flush_sink():
    """flush the log sink. call on session end."""
    if _flush is not None:
        try:
            _flush()
        except Exception:
            pass


def log(subsystem: str, level: str, message: str, **attrs):
    """log to console, record as span event, forward to sink. always."""
    ts = datetime.now().strftime("%H:%M:%S")
    prefix = f"[{ts} keanu:{subsystem}]"
    dest = sys.stderr if level in ("warn", "error") else sys.stdout
    print(f"{prefix} {message}", file=dest)

    # record as span event
    span = trace.get_current_span()
    if span and span.is_recording():
        span.add_event(
            f"keanu.{subsystem}.{level}",
            attributes={"message": message, "subsystem": subsystem, **attrs},
        )

    # forward to sink (ledger, etc) if registered
    if _sink is not None:
        try:
            _sink(subsystem, level, message, attrs if attrs else None)
        except Exception:
            pass  # sink errors never block the caller


def debug(subsystem: str, message: str, **attrs):
    log(subsystem, "debug", message, **attrs)


def info(subsystem: str, message: str, **attrs):
    log(subsystem, "info", message, **attrs)


def warn(subsystem: str, message: str, **attrs):
    log(subsystem, "warn", message, **attrs)


def error(subsystem: str, message: str, **attrs):
    log(subsystem, "error", message, **attrs)


# ============================================================
# MEMORY - remember and recall through the log
# ============================================================

# where the sink writes. gitstore puts JSONL here.
from keanu.paths import SHARED_DIR as MEMBERBERRY_DIR


def remember(content: str, memory_type: str = "fact", tags: list = None,
             importance: int = 5, **attrs):
    """log a memory. flows through the sink to git-backed JSONL.

    in the world: drop a stone in the river. the sink catches it,
    writes it to the bank. recall walks the bank later.
    """
    log("memory", "info", content,
        memory_type=memory_type,
        tags=",".join(tags or []),
        importance=str(importance),
        **attrs)


def recall(query: str, memory_type: str = None, limit: int = 10,
           log_dir: Path = None) -> list[dict]:
    """regex search over JSONL log files. newest first.

    in the world: walk the riverbank looking for stones you dropped.
    """
    search_dir = log_dir or MEMBERBERRY_DIR
    if not search_dir.exists():
        return []

    pattern = re.compile(re.escape(query), re.IGNORECASE) if query else None
    matches = []

    for jsonl_file in sorted(search_dir.rglob("*.jsonl"), reverse=True):
        try:
            with open(jsonl_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # filter by memory_type if given
                    if memory_type:
                        entry_type = entry.get("memory_type", "")
                        # check attrs dict too (log entries store it there)
                        if not entry_type or entry_type == "log":
                            attrs = entry.get("attrs") or {}
                            entry_type = attrs.get("memory_type", "")
                        if entry_type != memory_type:
                            continue

                    # match query against content
                    content = entry.get("content", "")
                    if pattern and not pattern.search(content):
                        # also search attrs for content
                        attrs = entry.get("attrs") or {}
                        attrs_str = json.dumps(attrs)
                        if not pattern.search(attrs_str):
                            continue

                    matches.append(entry)
                    if len(matches) >= limit:
                        return matches
        except OSError:
            continue

    return matches


# ============================================================
# SPAN CONTEXT MANAGERS - the key thing
# ============================================================

@contextmanager
def span(name: str, subsystem: str = "keanu", **attrs):
    """Create a traced span. Everything inside is connected.

    Usage:
        with span("remember", subsystem="memory", content="ship v1"):
            store.remember(memory)
            # any logs inside here are span events
            # any nested spans are children
            # the whole tree is one trace

    This is how memory becomes logging. Every remember() is a span.
    Every recall() is a span. The trace history IS the memory.
    """
    with _tracer.start_as_current_span(
        f"keanu.{subsystem}.{name}",
        attributes={f"keanu.{k}": str(v) for k, v in attrs.items()},
    ) as s:
        s.set_attribute("keanu.subsystem", subsystem)
        yield s


@contextmanager
def memory_span(operation: str, content: str = "", memory_type: str = "",
                tags: list = None, **attrs):
    """Span specifically for memory operations.

    Every memory operation becomes a traceable event.
    content + type + tags are first-class attributes.
    """
    with span(
        operation,
        subsystem="memory",
        operation=operation,
        content=content[:200],
        memory_type=memory_type,
        tags=",".join(tags or []),
        **attrs,
    ) as s:
        yield s


@contextmanager
def pulse_span(turn: int, **attrs):
    """Span for pulse checks. State transitions are trace events."""
    with span("check", subsystem="pulse", turn=turn, **attrs) as s:
        yield s
