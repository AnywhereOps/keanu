"""hooks.py - lightweight event bus for keanu.

fire events, subscribe handlers, react to what happens. abilities,
plugins, and the agent loop all speak the same language here.

handlers are ash. they run locally, no LLM needed. the bus just
makes sure everyone who cares gets the message. one bad handler
doesn't break the chain.

in the world: the nervous system sends signals. hooks are the
synapses. subscribe to what matters, ignore what doesn't.
"""

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Callable


# ============================================================
# WELL-KNOWN EVENTS
# ============================================================

BEFORE_EDIT = "before_edit"
AFTER_EDIT = "after_edit"
BEFORE_TEST = "before_test"
AFTER_TEST = "after_test"
ON_ERROR = "on_error"
BEFORE_COMMIT = "before_commit"
AFTER_COMMIT = "after_commit"
ABILITY_CALLED = "ability_called"
ORACLE_CALLED = "oracle_called"
LOOP_START = "loop_start"
LOOP_END = "loop_end"
PULSE_CHANGE = "pulse_change"


# ============================================================
# EVENT
# ============================================================

@dataclass
class Event:
    """a thing that happened."""
    name: str
    data: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    source: str = ""


# ============================================================
# TYPES
# ============================================================

HookFn = Callable[[Event], None]


# ============================================================
# EVENT BUS
# ============================================================

class EventBus:
    """subscribe, emit, react. handlers run in priority order."""

    def __init__(self, history_size: int = 200):
        # event_name -> list of (priority, fn) sorted desc by priority
        self._handlers: dict[str, list[tuple[int, HookFn]]] = defaultdict(list)
        self._history: deque[Event] = deque(maxlen=history_size)

    def subscribe(self, event_name: str, fn: HookFn, priority: int = 0):
        """register a handler. higher priority runs first."""
        bucket = self._handlers[event_name]
        bucket.append((priority, fn))
        bucket.sort(key=lambda x: x[0], reverse=True)

    def unsubscribe(self, event_name: str, fn: HookFn):
        """remove a handler."""
        bucket = self._handlers.get(event_name, [])
        self._handlers[event_name] = [
            (p, f) for p, f in bucket if f is not fn
        ]

    def emit(self, event_name: str, data: dict = None, source: str = ""):
        """fire an event. all handlers run, bad ones get caught."""
        event = Event(name=event_name, data=data or {}, source=source)
        self._history.append(event)
        for _pri, fn in self._handlers.get(event_name, []):
            try:
                fn(event)
            except Exception:
                pass  # one bad handler doesn't break the chain

    def emit_async(self, event_name: str, data: dict = None, source: str = ""):
        """fire an event and collect results from handlers."""
        event = Event(name=event_name, data=data or {}, source=source)
        self._history.append(event)
        results = []
        for _pri, fn in self._handlers.get(event_name, []):
            try:
                result = fn(event)
                results.append(result)
            except Exception:
                pass
        return results

    def listeners(self, event_name: str = "") -> dict[str, int]:
        """handler counts. one event or all of them."""
        if event_name:
            return {event_name: len(self._handlers.get(event_name, []))}
        return {k: len(v) for k, v in self._handlers.items() if v}

    def clear(self, event_name: str = ""):
        """remove handlers. one event or all of them."""
        if event_name:
            self._handlers.pop(event_name, None)
        else:
            self._handlers.clear()

    def history(self, limit: int = 50) -> list[Event]:
        """recent events, newest last."""
        items = list(self._history)
        return items[-limit:] if limit < len(items) else items


# ============================================================
# DEFAULT BUS + CONVENIENCE
# ============================================================

_bus = EventBus()


def on(name: str, fn: HookFn, priority: int = 0):
    """subscribe on the default bus."""
    _bus.subscribe(name, fn, priority)


def off(name: str, fn: HookFn):
    """unsubscribe from the default bus."""
    _bus.unsubscribe(name, fn)


def emit(name: str, data: dict = None, source: str = ""):
    """emit on the default bus."""
    _bus.emit(name, data, source)


def history(limit: int = 50) -> list[Event]:
    """recent events from the default bus."""
    return _bus.history(limit)


# ============================================================
# DECORATOR
# ============================================================

def on_event(name: str, priority: int = 0):
    """decorator. register a function as a handler on the default bus."""
    def decorator(fn: HookFn) -> HookFn:
        _bus.subscribe(name, fn, priority)
        return fn
    return decorator


# ============================================================
# FORMATTING
# ============================================================

def format_history(events: list[Event]) -> str:
    """pretty format event history for display."""
    if not events:
        return "(no events)"
    lines = []
    for e in events:
        ts = time.strftime("%H:%M:%S", time.localtime(e.timestamp))
        src = f" [{e.source}]" if e.source else ""
        data_str = ""
        if e.data:
            pairs = [f"{k}={v}" for k, v in e.data.items()]
            data_str = f" ({', '.join(pairs)})"
        lines.append(f"{ts} {e.name}{src}{data_str}")
    return "\n".join(lines)
