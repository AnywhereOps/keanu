"""log.py - subsystem logger + opentelemetry tracing.

every log is a span event. every operation is a span.
the trace IS the memory. logs become queryable, exportable,
connected across keanu <-> openpaw <-> whatever comes next.
"""

import sys
from datetime import datetime
from contextlib import contextmanager

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
    """Turn on span export to stderr. For debugging."""
    global _console_export
    if not _console_export:
        _provider.add_span_processor(
            SimpleSpanProcessor(ConsoleSpanExporter())
        )
        _console_export = True


def add_exporter(exporter):
    """Add a custom span exporter (OTLP, Jaeger, etc)."""
    _provider.add_span_processor(SimpleSpanProcessor(exporter))


def get_tracer():
    """Get the keanu tracer for custom instrumentation."""
    return _tracer


# ============================================================
# CONSOLE LOGGER (unchanged interface)
# ============================================================

LEVELS = {"debug": 0, "info": 1, "warn": 2, "error": 3}
_min_level = LEVELS["info"]
_sink = None
_flush = None


def set_level(level: str):
    global _min_level
    _min_level = LEVELS.get(level, 1)


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
    """log to console, record as span event, forward to sink."""
    if LEVELS.get(level, 1) >= _min_level:
        ts = datetime.now().strftime("%H:%M:%S")
        prefix = f"[{ts} keanu:{subsystem}]"
        dest = sys.stderr if level in ("warn", "error") else sys.stdout
        print(f"{prefix} {message}", file=dest)

    # always record as span event (even if below console threshold)
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
