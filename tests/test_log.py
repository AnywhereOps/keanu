"""Tests for log.py - subsystem logger + OpenTelemetry tracing."""

import io
import sys
from unittest.mock import patch

from keanu.log import log, info, warn, debug, error, set_level, span, memory_span, pulse_span


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
