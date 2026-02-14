"""Tests for compress/ - DNS, instructions, codec, executor, vectors, stack, exporter."""

import json
import pytest
from unittest.mock import MagicMock, patch

import numpy as np

from keanu.compress.dns import ContentDNS, sha256
from keanu.compress.instructions import COEFInstruction, COEFProgram
from keanu.compress.codec import (
    PatternRegistry, COEFEncoder, COEFDecoder, Pattern, Seed, Anchor, DecodeResult,
)
from keanu.compress.vectors import VectorStore, VectorEntry
from keanu.compress.stack import COEFStack
from keanu.compress.exporter import COEFSpanExporter, register_span_patterns, SPAN_PATTERNS


class TestDNS:
    def test_sha256_deterministic(self):
        assert sha256("hello") == sha256("hello")
        assert sha256("hello") != sha256("world")

    def test_store_and_resolve(self, tmp_path):
        dns = ContentDNS(str(tmp_path))
        h = dns.store("test content")
        assert dns.resolve(h) == "test content"

    def test_resolve_missing_raises(self, tmp_path):
        dns = ContentDNS(str(tmp_path))
        with pytest.raises(KeyError):
            dns.resolve("nonexistent")

    def test_has_missing(self, tmp_path):
        dns = ContentDNS(str(tmp_path))
        assert not dns.has("nonexistent")

    def test_has_present(self, tmp_path):
        dns = ContentDNS(str(tmp_path))
        h = dns.store("exists")
        assert dns.has(h)

    def test_store_idempotent(self, tmp_path):
        dns = ContentDNS(str(tmp_path))
        h1 = dns.store("same")
        h2 = dns.store("same")
        assert h1 == h2

    def test_store_with_name(self, tmp_path):
        dns = ContentDNS(str(tmp_path))
        dns.store("content", name="myfile")
        assert dns.resolve("myfile") == "content"

    def test_prefix_resolve(self, tmp_path):
        dns = ContentDNS(str(tmp_path))
        h = dns.store("content")
        assert dns.resolve(h[:16]) == "content"


class TestInstructions:
    def test_instruction_creation(self):
        inst = COEFInstruction(op="clone", args={"src": "abc123"})
        assert inst.op == "clone"

    def test_instruction_to_tokens(self):
        inst = COEFInstruction(op="clone", args={"src": "abc"})
        tokens = inst.to_tokens()
        assert "clone" in tokens
        assert "src=abc" in tokens

    def test_program_to_wire(self):
        p = COEFProgram(instructions=[
            COEFInstruction(op="clone", args={"src": "abc"}),
            COEFInstruction(op="rename", args={"old": "x", "new": "y"}),
        ])
        wire = p.to_wire()
        assert "clone" in wire
        assert "rename" in wire
        assert "|" in wire

    def test_program_from_wire(self):
        wire = "clone:src=abc | rename:old=x new=y"
        p = COEFProgram.from_wire(wire)
        assert len(p.instructions) == 2
        assert p.instructions[0].op == "clone"
        assert p.instructions[1].op == "rename"

    def test_roundtrip(self):
        original = COEFProgram(instructions=[
            COEFInstruction(op="literal", args={"text": "hello"}),
            COEFInstruction(op="store", args={}),
        ])
        wire = original.to_wire()
        restored = COEFProgram.from_wire(wire)
        assert len(restored.instructions) == len(original.instructions)
        assert restored.instructions[0].op == "literal"


class TestPatternRegistry:
    def test_get_missing_raises(self):
        reg = PatternRegistry()
        with pytest.raises(KeyError):
            reg.get("nonexistent_pattern_xyz")

    def test_register_and_get(self):
        reg = PatternRegistry()
        p = Pattern(
            pattern_id="test_custom",
            template="hello {{name}}",
            slots=["name"],
            description="test pattern",
        )
        reg.register(p)
        got = reg.get("test_custom")
        assert got.pattern_id == "test_custom"
        assert got.slots == ["name"]

    def test_list_patterns(self):
        reg = PatternRegistry()
        reg.register(Pattern(pattern_id="a", template="", slots=[], description=""))
        reg.register(Pattern(pattern_id="b", template="", slots=[], description=""))
        assert sorted(reg.list_patterns()) == ["a", "b"]

    def test_persistent_storage(self, tmp_path):
        reg1 = PatternRegistry(str(tmp_path))
        reg1.register(Pattern(pattern_id="saved", template="x", slots=[], description=""))
        reg2 = PatternRegistry(str(tmp_path))
        assert reg2.get("saved").pattern_id == "saved"


class TestSeedVector:
    def test_to_numeric(self):
        seed = Seed(
            pattern_id="test",
            anchors=[Anchor(key="k", value="v")],
            content_hash="abcdef1234567890" * 4,
        )
        numeric = seed.to_numeric()
        assert "pattern_idx" in numeric
        assert isinstance(numeric["pattern_idx"], int)
        assert len(numeric["anchor_hashes"]) == 1
        assert isinstance(numeric["content_hash_int"], int)

    def test_to_flat_array(self):
        seed = Seed(
            pattern_id="test",
            anchors=[],
            content_hash="abcdef1234567890" * 4,
        )
        vec = seed.to_flat_array(dim=20)
        assert vec.shape == (20,)
        assert not np.all(vec == 0)

    def test_to_flat_array_deterministic(self):
        seed1 = Seed(pattern_id="x", anchors=[], content_hash="aa" * 32)
        seed2 = Seed(pattern_id="y", anchors=[], content_hash="aa" * 32)
        np.testing.assert_array_equal(seed1.to_flat_array(), seed2.to_flat_array())

    def test_to_flat_array_different_hashes_differ(self):
        s1 = Seed(pattern_id="x", anchors=[], content_hash="aa" * 32)
        s2 = Seed(pattern_id="x", anchors=[], content_hash="bb" * 32)
        assert not np.array_equal(s1.to_flat_array(), s2.to_flat_array())


class TestVectorStore:
    def _make_seed(self, content: str) -> Seed:
        import hashlib
        h = hashlib.sha256(content.encode()).hexdigest()
        return Seed(pattern_id="test", anchors=[], content_hash=h)

    def test_embed_and_nearest(self):
        store = VectorStore(dim=20)
        seed = self._make_seed("hello world")
        vec = store.embed_seed(seed, "hello world")
        assert vec.shape == (20,)
        results = store.nearest(vec, k=1)
        assert len(results) == 1
        assert results[0][1] > 0.99  # near-perfect match

    def test_multiple_entries_nearest(self):
        store = VectorStore(dim=20)
        s1 = self._make_seed("alpha")
        s2 = self._make_seed("beta")
        s3 = self._make_seed("gamma")
        v1 = store.embed_seed(s1, "alpha")
        store.embed_seed(s2, "beta")
        store.embed_seed(s3, "gamma")
        results = store.nearest(v1, k=1)
        assert results[0][0].seed.content_hash == s1.content_hash

    def test_vector_to_seed(self):
        store = VectorStore(dim=20)
        seed = self._make_seed("test content")
        vec = store.embed_seed(seed, "test content")
        recovered, sim, content = store.vector_to_seed(vec)
        assert recovered.content_hash == seed.content_hash
        assert content == "test content"
        assert sim > 0.99

    def test_empty_store_raises(self):
        store = VectorStore()
        with pytest.raises(ValueError):
            store.vector_to_seed(np.zeros(20))

    def test_embed_semantic(self):
        store = VectorStore(dim=10)
        seed = self._make_seed("a longer semantic test with enough entropy for float64")
        vec = store.embed_semantic(seed, "a longer semantic test with enough entropy for float64")
        assert vec.shape == (10,)
        # should be normalized to unit length (or zero if degenerate)
        norm = np.linalg.norm(vec)
        assert norm > 0  # non-zero
        assert abs(norm - 1.0) < 0.01


class TestCOEFStack:
    def test_round_trip_lossless(self, tmp_path):
        reg = PatternRegistry()
        reg.register(Pattern(
            pattern_id="simple",
            template="hello {{name}} from {{place}}",
            slots=["name", "place"],
        ))
        dns = ContentDNS(str(tmp_path))
        stack = COEFStack(reg, dns=dns, vector_dim=20)

        result = stack.round_trip(
            content="hello drew from kc",
            pattern_id="simple",
            anchors={"name": "drew", "place": "kc"},
        )
        assert result["final_lossless"]
        assert result["recovered"] == "hello drew from kc"
        assert len(result["layers"]) == 4

    def test_words_to_numbers(self, tmp_path):
        reg = PatternRegistry()
        reg.register(Pattern(
            pattern_id="msg",
            template="{{content}}",
            slots=["content"],
        ))
        dns = ContentDNS(str(tmp_path))
        stack = COEFStack(reg, dns=dns)
        seed = stack.words_to_numbers("test", "msg", {"content": "test"})
        assert seed.pattern_id == "msg"
        assert seed.content_hash

    def test_numbers_to_words_dns(self, tmp_path):
        reg = PatternRegistry()
        reg.register(Pattern(
            pattern_id="msg",
            template="{{content}}",
            slots=["content"],
        ))
        dns = ContentDNS(str(tmp_path))
        stack = COEFStack(reg, dns=dns)
        seed = stack.words_to_numbers("test message", "msg", {"content": "test message"})
        result = stack.numbers_to_words(seed, use_dns=True)
        assert result["content"] == "test message"
        assert result["method"] == "dns_lookup"


class TestDecodeFromDNS:
    def test_decode_from_dns_hit(self, tmp_path):
        reg = PatternRegistry()
        dns = ContentDNS(str(tmp_path))
        h = dns.store("exact content here")
        decoder = COEFDecoder(reg)
        result = decoder.decode_from_dns(h, dns)
        assert result is not None
        assert result.content == "exact content here"
        assert result.is_lossless

    def test_decode_from_dns_miss(self, tmp_path):
        reg = PatternRegistry()
        dns = ContentDNS(str(tmp_path))
        decoder = COEFDecoder(reg)
        result = decoder.decode_from_dns("nonexistent_hash", dns)
        assert result is None


class TestSpanPatterns:
    def test_five_patterns_exist(self):
        assert len(SPAN_PATTERNS) == 5

    def test_register_span_patterns(self):
        reg = PatternRegistry()
        register_span_patterns(reg)
        assert "span.memory" in reg.list_patterns()
        assert "span.pulse" in reg.list_patterns()
        assert "span.alive" in reg.list_patterns()
        assert "span.cli" in reg.list_patterns()
        assert "span.generic" in reg.list_patterns()

    def test_register_idempotent(self):
        reg = PatternRegistry()
        register_span_patterns(reg)
        register_span_patterns(reg)  # should not raise
        assert len(reg.list_patterns()) == 5


class TestCOEFSpanExporter:
    def _make_mock_span(self, name="keanu.memory.remember", **attrs):
        span = MagicMock()
        span.name = name
        span.start_time = 1707868800000000000  # 2024-02-14 in nanoseconds
        span.context = MagicMock()
        span.context.span_id = 0x1234567890ABCDEF
        span.context.trace_id = 0xABCDEF1234567890
        default_attrs = {
            "keanu.subsystem": "memory",
            "keanu.operation": "remember",
            "keanu.content": "ship v1",
            "keanu.memory_type": "goal",
            "keanu.tags": "build,career",
        }
        default_attrs.update(attrs)
        span.attributes = default_attrs
        return span

    def test_export_stores_in_dns(self, tmp_path):
        dns = ContentDNS(str(tmp_path))
        reg = PatternRegistry()
        register_span_patterns(reg)
        exporter = COEFSpanExporter(dns=dns, registry=reg)

        span = self._make_mock_span()
        result = exporter.export([span])

        from opentelemetry.sdk.trace.export import SpanExportResult
        assert result == SpanExportResult.SUCCESS
        # should have stored span content and seed
        names = dns.names()
        assert any(n.startswith("span:") for n in names)
        assert any(n.startswith("seed:") for n in names)

    def test_export_creates_decodable_seed(self, tmp_path):
        dns = ContentDNS(str(tmp_path))
        reg = PatternRegistry()
        register_span_patterns(reg)
        exporter = COEFSpanExporter(dns=dns, registry=reg)
        decoder = COEFDecoder(reg)

        span = self._make_mock_span()
        exporter.export([span])

        # find the seed
        names = dns.names()
        seed_name = [n for n in names if n.startswith("seed:")][0]
        compact = dns.resolve(seed_name)
        seed = Seed.from_compact(compact)
        result = decoder.decode(seed)
        assert "memory" in result.content
        assert "ship v1" in result.content

    def test_export_with_memory_store(self, tmp_path):
        dns = ContentDNS(str(tmp_path))
        reg = PatternRegistry()
        register_span_patterns(reg)

        mock_store = MagicMock()
        mock_store.remember = MagicMock(return_value="test-id")

        exporter = COEFSpanExporter(dns=dns, registry=reg, store=mock_store)
        span = self._make_mock_span()
        exporter.export([span])

        mock_store.remember.assert_called_once()
        memory_arg = mock_store.remember.call_args[0][0]
        assert memory_arg.content.startswith("COEF::")
        assert "coef" in memory_arg.tags
        assert "trace" in memory_arg.tags

    def test_export_handles_errors_gracefully(self, tmp_path):
        dns = ContentDNS(str(tmp_path))
        reg = PatternRegistry()
        # deliberately don't register patterns - should not crash
        exporter = COEFSpanExporter(dns=dns, registry=reg)

        span = self._make_mock_span()
        from opentelemetry.sdk.trace.export import SpanExportResult
        result = exporter.export([span])
        assert result == SpanExportResult.SUCCESS  # error swallowed

    def test_pattern_matching(self, tmp_path):
        dns = ContentDNS(str(tmp_path))
        reg = PatternRegistry()
        register_span_patterns(reg)
        exporter = COEFSpanExporter(dns=dns, registry=reg)

        assert exporter._match_pattern(self._make_mock_span("keanu.memory.remember")) == "span.memory"
        assert exporter._match_pattern(self._make_mock_span("keanu.pulse.check")) == "span.pulse"
        assert exporter._match_pattern(self._make_mock_span("keanu.alive.diagnose")) == "span.alive"
        assert exporter._match_pattern(self._make_mock_span("keanu.cli.decode")) == "span.cli"
        assert exporter._match_pattern(self._make_mock_span("keanu.unknown.thing")) == "span.generic"
        assert exporter._match_pattern(self._make_mock_span("something")) == "span.generic"
