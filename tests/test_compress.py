"""Tests for compress/ - DNS, instructions, codec, executor."""

import pytest

from keanu.compress.dns import ContentDNS, sha256
from keanu.compress.instructions import COEFInstruction, COEFProgram
from keanu.compress.codec import PatternRegistry, COEFEncoder, COEFDecoder, Pattern


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
