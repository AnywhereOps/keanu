#!/usr/bin/env python3
"""
COEF: Compressed Observation-Execution Framework
Lossless Encoder / Decoder

Send the barcode AND the color name. Full signal, verified.
No ML. No GPU. No training loop. Templates, slots, and hashes.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path


# ===== DATA STRUCTURES =====

@dataclass
class Anchor:
    """A fixed point that cannot drift during decode."""
    key: str
    value: str
    anchor_type: str = "literal"


@dataclass
class Seed:
    """The compressed representation. This is what travels."""
    pattern_id: str
    anchors: list[Anchor]
    content_hash: str
    metadata: dict = field(default_factory=dict)
    version: str = "coef-v1"

    def to_compact(self) -> str:
        """Serialize to minimal wire format. Uses JSON for anchors to handle special chars."""
        anchor_data = [
            {"k": a.key, "v": a.value, "t": a.anchor_type[0]}
            for a in self.anchors
        ]
        anchor_json = json.dumps(anchor_data, separators=(',', ':'))
        return f"COEF::{self.version}::{self.pattern_id}::{self.content_hash[:16]}::{anchor_json}"

    @classmethod
    def from_compact(cls, compact: str) -> "Seed":
        # Split only first 4 :: delimiters; the rest is JSON (may contain ::)
        parts = compact.split("::", 4)
        if parts[0] != "COEF" or len(parts) < 5:
            raise ValueError(f"Invalid COEF seed: {compact[:50]}...")
        anchors = []
        anchor_data = json.loads(parts[4])
        for item in anchor_data:
            anchors.append(Anchor(
                key=item["k"], value=item["v"],
                anchor_type="literal" if item["t"] == "l" else "structural"
            ))
        return cls(
            pattern_id=parts[2], anchors=anchors,
            content_hash=parts[3], version=parts[1],
        )


@dataclass
class Pattern:
    """A reference template. Training = committing patterns."""
    pattern_id: str
    template: str
    slots: list[str]
    description: str = ""

    def validate_anchors(self, anchors: list[Anchor]) -> list[str]:
        provided = {a.key for a in anchors}
        required = set(self.slots)
        missing = required - provided
        return [f"Missing: {missing}"] if missing else []


@dataclass
class DecodeResult:
    """Decoder output with verification."""
    content: str
    content_hash: str
    expected_hash: str
    is_lossless: bool
    drift_report: str = ""
    compression_ratio: float = 0.0


# ===== PATTERN REGISTRY =====

class PatternRegistry:
    """The pattern library. This IS the model weights."""

    def __init__(self, storage_dir: Optional[str] = None):
        self._patterns: dict[str, Pattern] = {}
        self._storage_dir = Path(storage_dir) if storage_dir else None
        if self._storage_dir:
            self._storage_dir.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    def register(self, pattern: Pattern):
        self._patterns[pattern.pattern_id] = pattern
        if self._storage_dir:
            path = self._storage_dir / f"{pattern.pattern_id}.json"
            with open(path, "w") as f:
                json.dump(asdict(pattern), f, indent=2)

    def get(self, pattern_id: str) -> Pattern:
        if pattern_id not in self._patterns:
            raise KeyError(f"Pattern '{pattern_id}' not found. Have: {list(self._patterns.keys())}")
        return self._patterns[pattern_id]

    def list_patterns(self) -> list[str]:
        return list(self._patterns.keys())

    def _load_from_disk(self):
        for path in self._storage_dir.glob("*.json"):
            with open(path) as f:
                data = json.load(f)
                self._patterns[data["pattern_id"]] = Pattern(**data)


# ===== ENCODER =====

class COEFEncoder:
    """Compresses full content into a seed."""

    def __init__(self, registry: PatternRegistry):
        self.registry = registry

    def encode(self, content: str, pattern_id: str,
               anchor_overrides: Optional[dict[str, str]] = None) -> Seed:
        pattern = self.registry.get(pattern_id)
        content_hash = _sha256(content)

        if anchor_overrides:
            anchors = [
                Anchor(key=k, value=v, anchor_type="literal")
                for k, v in anchor_overrides.items()
            ]
        else:
            anchors = self._auto_extract(content, pattern)

        errors = pattern.validate_anchors(anchors)
        if errors:
            raise ValueError(f"Anchor validation failed: {errors}")

        return Seed(
            pattern_id=pattern_id, anchors=anchors, content_hash=content_hash,
        )

    def _auto_extract(self, content: str, pattern: Pattern) -> list[Anchor]:
        regex_parts = []
        slot_order = []
        remaining = pattern.template
        while "{{" in remaining:
            before, rest = remaining.split("{{", 1)
            slot_name, after = rest.split("}}", 1)
            regex_parts.append(re.escape(before))
            regex_parts.append(f"(?P<{slot_name}>.+?)")
            slot_order.append(slot_name)
            remaining = after
        regex_parts.append(re.escape(remaining))
        match = re.match("".join(regex_parts), content, re.DOTALL)
        if not match:
            raise ValueError("Auto-extraction failed. Provide anchor_overrides.")
        return [
            Anchor(key=s, value=match.group(s).strip(), anchor_type="literal")
            for s in slot_order
        ]


# ===== DECODER =====

class COEFDecoder:
    """Expands a seed back into full content. Mechanical, not creative."""

    def __init__(self, registry: PatternRegistry):
        self.registry = registry

    def decode(self, seed: Seed) -> DecodeResult:
        pattern = self.registry.get(seed.pattern_id)
        anchor_map = {a.key: a.value for a in seed.anchors}

        content = pattern.template
        for slot in pattern.slots:
            placeholder = "{{" + slot + "}}"
            content = content.replace(
                placeholder, anchor_map.get(slot, f"[MISSING:{slot}]")
            )

        content_hash = _sha256(content)
        expected = seed.content_hash
        is_lossless = (
            content_hash.startswith(expected) or expected.startswith(content_hash)
        )

        drift_report = ""
        if not is_lossless:
            drift_report = (
                f"DRIFT DETECTED\n"
                f"  Expected: {expected[:16]}\n"
                f"  Got:      {content_hash[:16]}\n"
                f"  Anchors:  {json.dumps(anchor_map, indent=2)}"
            )

        seed_size = len(seed.to_compact())
        ratio = len(content) / seed_size if seed_size > 0 else 0

        return DecodeResult(
            content=content, content_hash=content_hash,
            expected_hash=expected, is_lossless=is_lossless,
            drift_report=drift_report, compression_ratio=ratio,
        )


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ===== BUILT-IN PATTERNS =====

BUILTIN_PATTERNS = [
    Pattern(
        pattern_id="python_function",
        template='def {{func_name}}({{params}}):\n    """{{docstring}}"""\n    {{body}}',
        slots=["func_name", "params", "docstring", "body"],
        description="Standard Python function",
    ),
    Pattern(
        pattern_id="python_class",
        template=(
            'class {{class_name}}({{base_classes}}):\n'
            '    """{{docstring}}"""\n\n'
            '    def __init__(self, {{init_params}}):\n'
            '        {{init_body}}'
        ),
        slots=["class_name", "base_classes", "docstring", "init_params", "init_body"],
        description="Python class with __init__",
    ),
    Pattern(
        pattern_id="color_reading",
        template="[{{source}}] {{symbol}} {{state}} R:{{red}} Y:{{yellow}} B:{{blue}} wise:{{wise}}",
        slots=["source", "symbol", "state", "red", "yellow", "blue", "wise"],
        description="Compressed color reading",
    ),
    Pattern(
        pattern_id="signal_message",
        template="[{{sender}}@{{context}}] {{signal}} -> {{action}}",
        slots=["sender", "context", "signal", "action"],
        description="COEF signal for human-AI communication",
    ),
]
