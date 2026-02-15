"""Tests for log.py - subsystem logger + OpenTelemetry tracing + sink."""

import io
import sys
from unittest.mock import patch, MagicMock

from keanu.log import log, info, warn, debug, error, set_level, set_sink, flush_sink, span, memory_span, pulse_span


class TestConsoleLogger:
    def test_info_prints_to_stdout(self, capsys):
        info("test", "hello world")
        captured = capsys.readouterr()
        assert "keanu:test" in captured.out
        assert "hello world" in captured.out

    def test_warn_prints_to_stderr(self, capsys):
        warn("test", "danger")
        captured = capsys.readouterr()
        assert "keanu:test" in captured.err
        assert "danger" in captured.err

    def test_error_prints_to_stderr(self, capsys):
        error("test", "broke")
        captured = capsys.readouterr()
        assert "broke" in captured.err

    def test_debug_hidden_by_default(self, capsys):
        debug("test", "verbose")
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_set_level_debug(self, capsys):
        set_level("debug")
        debug("test", "now visible")
        captured = capsys.readouterr()
        assert "now visible" in captured.out
        set_level("info")  # reset

    def test_set_level_warn(self, capsys):
        set_level("warn")
        info("test", "hidden")
        captured = capsys.readouterr()
        assert captured.out == ""
        set_level("info")  # reset


class TestSpans:
    def test_span_context_manager(self):
        with span("test_op", subsystem="test") as s:
            assert s is not None
            s.set_attribute("keanu.custom", "value")

    def test_memory_span(self):
        with memory_span("remember", content="ship v1", memory_type="goal",
                         tags=["build"]) as s:
            assert s is not None

    def test_pulse_span(self):
        with pulse_span(turn=1) as s:
            assert s is not None

    def test_nested_spans(self):
        with span("outer", subsystem="test"):
            with span("inner", subsystem="test") as s:
                assert s is not None

    def test_log_inside_span(self, capsys):
        with span("test_op", subsystem="test"):
            info("test", "inside a span")
        captured = capsys.readouterr()
        assert "inside a span" in captured.out


class TestSink:
    def setup_method(self):
        set_sink(None)

    def teardown_method(self):
        set_sink(None)

    def test_sink_receives_log(self):
        calls = []
        set_sink(lambda sub, lvl, msg, attrs: calls.append((sub, lvl, msg, attrs)))
        info("test", "hello sink")
        assert len(calls) == 1
        assert calls[0][0] == "test"
        assert calls[0][1] == "info"
        assert calls[0][2] == "hello sink"

    def test_sink_receives_attrs(self):
        calls = []
        set_sink(lambda sub, lvl, msg, attrs: calls.append(attrs))
        log("test", "info", "with attrs", key="val")
        assert calls[0] == {"key": "val"}

    def test_sink_none_attrs_when_empty(self):
        calls = []
        set_sink(lambda sub, lvl, msg, attrs: calls.append(attrs))
        info("test", "no attrs")
        assert calls[0] is None

    def test_sink_error_doesnt_crash(self, capsys):
        def bad_sink(sub, lvl, msg, attrs):
            raise RuntimeError("boom")
        set_sink(bad_sink)
        info("test", "still works")
        captured = capsys.readouterr()
        assert "still works" in captured.out

    def test_set_sink_clears(self):
        calls = []
        set_sink(lambda sub, lvl, msg, attrs: calls.append(1))
        info("test", "one")
        set_sink(None)
        info("test", "two")
        assert len(calls) == 1

    def test_flush_sink(self):
        flushed = []
        set_sink(lambda *a: None, flush_fn=lambda: flushed.append(True))
        flush_sink()
        assert len(flushed) == 1

    def test_flush_sink_noop_without_flush_fn(self):
        set_sink(lambda *a: None)
        flush_sink()  # should not raise
