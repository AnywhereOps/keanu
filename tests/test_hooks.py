"""Tests for hooks.py - the event bus."""

import keanu.abilities.world.hooks as hooks
from keanu.abilities.world.hooks import Event, EventBus, on_event, format_history


class TestEventBus:
    def test_subscribe_and_emit(self):
        bus = EventBus()
        received = []
        bus.subscribe("ping", lambda e: received.append(e.name))
        bus.emit("ping")
        assert received == ["ping"]

    def test_priority_ordering(self):
        bus = EventBus()
        order = []
        bus.subscribe("go", lambda e: order.append("low"), priority=0)
        bus.subscribe("go", lambda e: order.append("high"), priority=10)
        bus.subscribe("go", lambda e: order.append("mid"), priority=5)
        bus.emit("go")
        assert order == ["high", "mid", "low"]

    def test_unsubscribe(self):
        bus = EventBus()
        received = []
        fn = lambda e: received.append(1)
        bus.subscribe("x", fn)
        bus.emit("x")
        bus.unsubscribe("x", fn)
        bus.emit("x")
        assert received == [1]

    def test_unsubscribe_missing_is_safe(self):
        bus = EventBus()
        bus.unsubscribe("nope", lambda e: None)  # no error

    def test_handler_exception_isolation(self):
        bus = EventBus()
        results = []

        def bad(e):
            raise ValueError("boom")

        def good(e):
            results.append("ok")

        bus.subscribe("test", bad, priority=10)
        bus.subscribe("test", good, priority=0)
        bus.emit("test")
        assert results == ["ok"]

    def test_history_tracking(self):
        bus = EventBus()
        bus.emit("a")
        bus.emit("b")
        bus.emit("c")
        h = bus.history()
        assert [e.name for e in h] == ["a", "b", "c"]

    def test_history_limit(self):
        bus = EventBus()
        for i in range(10):
            bus.emit(f"e{i}")
        h = bus.history(limit=3)
        assert len(h) == 3
        assert h[-1].name == "e9"

    def test_history_circular_buffer(self):
        bus = EventBus(history_size=5)
        for i in range(10):
            bus.emit(f"e{i}")
        h = bus.history()
        assert len(h) == 5
        assert h[0].name == "e5"

    def test_clear_specific(self):
        bus = EventBus()
        bus.subscribe("a", lambda e: None)
        bus.subscribe("b", lambda e: None)
        bus.clear("a")
        assert bus.listeners("a") == {"a": 0}
        assert bus.listeners("b") == {"b": 1}

    def test_clear_all(self):
        bus = EventBus()
        bus.subscribe("a", lambda e: None)
        bus.subscribe("b", lambda e: None)
        bus.clear()
        assert bus.listeners() == {}

    def test_listeners_counts(self):
        bus = EventBus()
        bus.subscribe("x", lambda e: None)
        bus.subscribe("x", lambda e: None)
        bus.subscribe("y", lambda e: None)
        counts = bus.listeners()
        assert counts == {"x": 2, "y": 1}

    def test_listeners_single(self):
        bus = EventBus()
        bus.subscribe("x", lambda e: None)
        assert bus.listeners("x") == {"x": 1}
        assert bus.listeners("nope") == {"nope": 0}

    def test_event_data_and_source(self):
        bus = EventBus()
        captured = []
        bus.subscribe("info", lambda e: captured.append(e))
        bus.emit("info", data={"key": "val"}, source="test")
        assert captured[0].data == {"key": "val"}
        assert captured[0].source == "test"
        assert captured[0].timestamp > 0

    def test_multiple_handlers_same_event(self):
        bus = EventBus()
        results = []
        bus.subscribe("multi", lambda e: results.append("a"))
        bus.subscribe("multi", lambda e: results.append("b"))
        bus.emit("multi")
        assert len(results) == 2
        assert "a" in results and "b" in results

    def test_emit_async_collects_results(self):
        bus = EventBus()
        bus.subscribe("calc", lambda e: 42)
        bus.subscribe("calc", lambda e: 99)
        results = bus.emit_async("calc")
        assert results == [42, 99]

    def test_emit_no_handlers(self):
        bus = EventBus()
        bus.emit("ghost")  # no error
        h = bus.history()
        assert h[0].name == "ghost"


class TestModuleLevelConvenience:
    def setup_method(self):
        hooks._bus.clear()
        hooks._bus._history.clear()

    def test_on_and_emit(self):
        received = []
        fn = lambda e: received.append(e.name)
        hooks.on("ping", fn)
        hooks.emit("ping")
        assert received == ["ping"]
        hooks.off("ping", fn)

    def test_off(self):
        received = []
        fn = lambda e: received.append(1)
        hooks.on("x", fn)
        hooks.off("x", fn)
        hooks.emit("x")
        assert received == []

    def test_history(self):
        hooks.emit("a", source="test")
        h = hooks.history()
        assert len(h) == 1
        assert h[0].name == "a"


class TestOnEventDecorator:
    def setup_method(self):
        hooks._bus.clear()
        hooks._bus._history.clear()

    def test_decorator_registers(self):
        results = []

        @on_event("decorated")
        def handler(e):
            results.append(e.data)

        hooks.emit("decorated", data={"x": 1})
        assert results == [{"x": 1}]
        hooks.off("decorated", handler)

    def test_decorator_with_priority(self):
        order = []

        @on_event("pri", priority=10)
        def first(e):
            order.append("first")

        @on_event("pri", priority=0)
        def second(e):
            order.append("second")

        hooks.emit("pri")
        assert order == ["first", "second"]
        hooks.off("pri", first)
        hooks.off("pri", second)


class TestFormatHistory:
    def test_empty(self):
        assert format_history([]) == "(no events)"

    def test_with_events(self):
        events = [
            Event(name="test", data={"k": "v"}, source="src"),
            Event(name="plain"),
        ]
        out = format_history(events)
        assert "test" in out
        assert "[src]" in out
        assert "k=v" in out
        assert "plain" in out


class TestWellKnownEvents:
    def test_constants_exist(self):
        assert hooks.BEFORE_EDIT == "before_edit"
        assert hooks.AFTER_EDIT == "after_edit"
        assert hooks.BEFORE_TEST == "before_test"
        assert hooks.AFTER_TEST == "after_test"
        assert hooks.ON_ERROR == "on_error"
        assert hooks.BEFORE_COMMIT == "before_commit"
        assert hooks.AFTER_COMMIT == "after_commit"
        assert hooks.ABILITY_CALLED == "ability_called"
        assert hooks.ORACLE_CALLED == "oracle_called"
        assert hooks.LOOP_START == "loop_start"
        assert hooks.LOOP_END == "loop_end"
        assert hooks.PULSE_CHANGE == "pulse_change"
