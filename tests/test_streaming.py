"""tests for oracle streaming support."""

import json
from unittest.mock import patch, MagicMock

from keanu.oracle import (
    stream_oracle, collect_stream,
    _stream_cloud, _stream_local,
)


class _FakeResponse:
    """fake requests response for streaming tests."""
    def __init__(self, chunks, status_code=200):
        self.chunks = chunks
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def iter_lines(self):
        for chunk in self.chunks:
            if isinstance(chunk, str):
                yield chunk.encode("utf-8")
            else:
                yield chunk


def _make_cloud_events(text_chunks):
    """build anthropic SSE lines from text chunks."""
    lines = []
    # message_start
    lines.append(f'data: {json.dumps({"type": "message_start", "message": {"usage": {"input_tokens": 10}}})}')
    for chunk in text_chunks:
        event = {
            "type": "content_block_delta",
            "delta": {"text": chunk},
        }
        lines.append(f"data: {json.dumps(event)}")
    # message_delta with output tokens
    lines.append(f'data: {json.dumps({"type": "message_delta", "usage": {"output_tokens": 20}})}')
    lines.append("data: [DONE]")
    return lines


def _make_ollama_events(text_chunks):
    """build ollama JSONL lines from text chunks."""
    lines = []
    for chunk in text_chunks:
        lines.append(json.dumps({"response": chunk, "done": False}))
    lines.append(json.dumps({"response": "", "done": True}))
    return lines


class TestStreamCloud:

    def test_yields_chunks(self):
        events = _make_cloud_events(["Hello", " world", "!"])
        response = _FakeResponse(events)

        legend = MagicMock()
        legend.endpoint = "https://api.anthropic.com/v1/messages"
        legend.name = "test"

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("keanu.oracle.requests.post", return_value=response):
                chunks = list(_stream_cloud("test", "", legend, "test-model", None, 0))

        assert chunks == ["Hello", " world", "!"]

    def test_calls_on_token(self):
        events = _make_cloud_events(["a", "b"])
        response = _FakeResponse(events)

        legend = MagicMock()
        legend.endpoint = "https://api.anthropic.com/v1/messages"
        legend.name = "test"

        received = []

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("keanu.oracle.requests.post", return_value=response):
                list(_stream_cloud("test", "", legend, "test-model", received.append, 0))

        assert received == ["a", "b"]

    def test_no_api_key(self):
        legend = MagicMock()
        legend.endpoint = "https://api.anthropic.com/v1/messages"

        with patch.dict("os.environ", {}, clear=True):
            chunks = list(_stream_cloud("test", "", legend, "test-model", None, 0))
        assert chunks == []


class TestStreamLocal:

    def test_yields_chunks(self):
        events = _make_ollama_events(["Hello", " world"])
        response = _FakeResponse(events)

        legend = MagicMock()
        legend.endpoint = "http://localhost:11434/api/generate"

        with patch("keanu.oracle.requests.post", return_value=response):
            chunks = list(_stream_local("test", "", legend, "test-model", None, 0))

        assert chunks == ["Hello", " world"]


class TestCollectStream:

    def test_collects_full_response(self):
        events = _make_cloud_events(["Hello", " ", "world"])
        response = _FakeResponse(events)

        legend = MagicMock()
        legend.endpoint = "https://api.anthropic.com/v1/messages"
        legend.name = "test"
        legend.model = "test-model"
        legend.reach = "cloud"

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("keanu.oracle.requests.post", return_value=response):
                with patch("keanu.oracle.load_legend", return_value=legend):
                    result = collect_stream("test", legend=legend)

        assert result == "Hello world"


class TestStreamOracle:

    def test_dispatches_to_cloud(self):
        events = _make_cloud_events(["ok"])
        response = _FakeResponse(events)

        legend = MagicMock()
        legend.endpoint = "https://api.anthropic.com/v1/messages"
        legend.name = "test"
        legend.model = "test-model"
        legend.reach = "cloud"

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("keanu.oracle.requests.post", return_value=response):
                with patch("keanu.oracle.load_legend", return_value=legend):
                    chunks = list(stream_oracle("test", legend=legend))

        assert chunks == ["ok"]

    def test_dispatches_to_local(self):
        events = _make_ollama_events(["hi"])
        response = _FakeResponse(events)

        legend = MagicMock()
        legend.endpoint = "http://localhost:11434/api/generate"
        legend.name = "test"
        legend.model = "test-model"
        legend.reach = "local"

        with patch("keanu.oracle.requests.post", return_value=response):
            with patch("keanu.oracle.load_legend", return_value=legend):
                chunks = list(stream_oracle("test", legend=legend))

        assert chunks == ["hi"]
