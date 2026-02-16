"""tests for telemetry and tracing."""

from unittest.mock import patch

from keanu.abilities.world.telemetry import (
    Span, start_span, end_span, get_active_spans, trace_span,
    get_spans, analyze_traces, trace_summary, TraceStats,
    _ACTIVE_SPANS,
)


class TestSpan:

    def test_auto_ids(self):
        s = Span(name="test")
        assert s.span_id.startswith("s_")
        assert s.trace_id.startswith("t_")
        assert s.start_time > 0

    def test_duration(self):
        s = Span(name="test", start_time=100.0, end_time=100.5)
        assert s.duration_ms == 500

    def test_add_event(self):
        s = Span(name="test")
        s.add_event("checkpoint", data="x")
        assert len(s.events) == 1
        assert s.events[0]["name"] == "checkpoint"
        assert s.events[0]["data"] == "x"

    def test_set_error(self):
        s = Span(name="test")
        s.set_error("boom")
        assert s.status == "error"
        assert s.attributes["error"] == "boom"

    def test_to_dict(self):
        s = Span(name="test")
        d = s.to_dict()
        assert d["name"] == "test"
        assert "span_id" in d
        assert "trace_id" in d


class TestSpanManagement:

    def setup_method(self):
        _ACTIVE_SPANS.clear()

    def test_start_and_end(self, tmp_path):
        log_file = tmp_path / "spans.jsonl"
        with patch("keanu.abilities.world.telemetry._SPANS_LOG", log_file):
            span = start_span("test_op", model="opus")
            assert span.span_id in _ACTIVE_SPANS
            assert span.attributes["model"] == "opus"

            end_span(span)
            assert span.span_id not in _ACTIVE_SPANS
            assert span.end_time > 0

    def test_get_active_spans(self):
        s1 = start_span("a")
        s2 = start_span("b")
        active = get_active_spans()
        assert len(active) == 2
        # cleanup
        _ACTIVE_SPANS.clear()


class TestTraceSpan:

    def test_context_manager(self, tmp_path):
        log_file = tmp_path / "spans.jsonl"
        with patch("keanu.abilities.world.telemetry._SPANS_LOG", log_file):
            with trace_span("test_block") as span:
                span.add_event("inside")
            assert span.end_time > 0
            assert span.status == "ok"

    def test_captures_error(self, tmp_path):
        log_file = tmp_path / "spans.jsonl"
        with patch("keanu.abilities.world.telemetry._SPANS_LOG", log_file):
            try:
                with trace_span("error_block") as span:
                    raise ValueError("test error")
            except ValueError:
                pass
            assert span.status == "error"
            assert "test error" in span.attributes["error"]


class TestPersistence:

    def test_write_and_read(self, tmp_path):
        log_file = tmp_path / "spans.jsonl"
        with patch("keanu.abilities.world.telemetry._SPANS_LOG", log_file):
            span = start_span("op1")
            end_span(span)
            span2 = start_span("op2")
            end_span(span2)

            spans = get_spans()
        assert len(spans) == 2
        assert spans[0]["name"] == "op1"

    def test_empty_log(self, tmp_path):
        log_file = tmp_path / "spans.jsonl"
        with patch("keanu.abilities.world.telemetry._SPANS_LOG", log_file):
            spans = get_spans()
        assert spans == []

    def test_filter_by_trace(self, tmp_path):
        log_file = tmp_path / "spans.jsonl"
        with patch("keanu.abilities.world.telemetry._SPANS_LOG", log_file):
            s1 = start_span("a", trace_id="trace1")
            end_span(s1)
            s2 = start_span("b", trace_id="trace2")
            end_span(s2)

            spans = get_spans(trace_id="trace1")
        assert len(spans) == 1
        assert spans[0]["trace_id"] == "trace1"


class TestAnalyzeTraces:

    def test_basic_stats(self):
        spans = [
            {"name": "oracle", "trace_id": "t1", "duration_ms": 100, "status": "ok", "attributes": {"tokens": 500}},
            {"name": "oracle", "trace_id": "t1", "duration_ms": 200, "status": "ok", "attributes": {"tokens": 300}},
            {"name": "ability", "trace_id": "t2", "duration_ms": 10, "status": "error", "attributes": {}},
        ]
        stats = analyze_traces(spans)
        assert stats.total_spans == 3
        assert stats.total_traces == 2
        assert stats.total_tokens == 800
        assert stats.error_rate > 0

    def test_by_name(self):
        spans = [
            {"name": "oracle", "trace_id": "t1", "duration_ms": 100, "status": "ok", "attributes": {}},
            {"name": "oracle", "trace_id": "t1", "duration_ms": 200, "status": "ok", "attributes": {}},
            {"name": "ability", "trace_id": "t2", "duration_ms": 10, "status": "ok", "attributes": {}},
        ]
        stats = analyze_traces(spans)
        assert "oracle" in stats.by_name
        assert stats.by_name["oracle"]["count"] == 2

    def test_empty(self):
        stats = analyze_traces([])
        assert stats.total_spans == 0


class TestTraceSummary:

    def test_returns_dict(self, tmp_path):
        log_file = tmp_path / "spans.jsonl"
        with patch("keanu.abilities.world.telemetry._SPANS_LOG", log_file):
            summary = trace_summary(days=7)
        assert "period_days" in summary
        assert summary["total_spans"] == 0
