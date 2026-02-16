"""exporter.py - OpenTelemetry SpanExporter that encodes spans as COEF seeds.

The bridge between tracing and memory. Every completed span becomes:
1. A COEF Seed (compressed, hash-verified)
2. A ContentDNS entry (lossless retrieval by hash)
3. Optionally a memberberry memory (searchable)

Memory becomes logging. Logging becomes memory.
"""

from datetime import datetime, timezone
from typing import Optional, Sequence

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from .codec import Pattern, PatternRegistry, COEFEncoder, COEFDecoder, Seed, Anchor
from .dns import ContentDNS


# ============================================================
# SPAN PATTERNS - one per subsystem
# ============================================================

SPAN_PATTERNS = [
    Pattern(
        pattern_id="span.memory",
        template="[{{timestamp}}] memory.{{operation}} type={{memory_type}} tags={{tags}} | {{content}}",
        slots=["timestamp", "operation", "memory_type", "tags", "content"],
        description="Memory operation span (remember, recall)",
    ),
    Pattern(
        pattern_id="span.pulse",
        template="[{{timestamp}}] pulse turn={{turn}} state={{state}} ok={{ok}} wise={{wise_mind}} | {{nudge}}",
        slots=["timestamp", "turn", "state", "ok", "wise_mind", "nudge"],
        description="Pulse heartbeat check",
    ),
    Pattern(
        pattern_id="span.alive",
        template="[{{timestamp}}] alive state={{state}} color={{color}} wise={{wise}} | {{evidence}}",
        slots=["timestamp", "state", "color", "wise", "evidence"],
        description="ALIVE diagnostic",
    ),
    Pattern(
        pattern_id="span.cli",
        template="[{{timestamp}}] cli.{{command}} | {{result}}",
        slots=["timestamp", "command", "result"],
        description="CLI command execution",
    ),
    Pattern(
        pattern_id="span.generic",
        template="[{{timestamp}}] {{subsystem}}.{{operation}} | {{attrs}}",
        slots=["timestamp", "subsystem", "operation", "attrs"],
        description="Catch-all for any span",
    ),
]


def register_span_patterns(registry: PatternRegistry):
    """Register the 5 span patterns into a registry."""
    for pattern in SPAN_PATTERNS:
        try:
            registry.get(pattern.pattern_id)
        except KeyError:
            registry.register(pattern)


# ============================================================
# EXPORTER
# ============================================================

class COEFSpanExporter(SpanExporter):
    """Turns OpenTelemetry spans into COEF seeds.

    Every completed span:
    1. Gets matched to a subsystem pattern
    2. Span attributes become pattern anchors
    3. Encoded into a Seed via COEFEncoder
    4. Stored in ContentDNS (lossless, hash-addressable)
    5. Optionally stored as a memberberry memory
    """

    def __init__(self, dns: ContentDNS, registry: PatternRegistry,
                 store=None):
        self.dns = dns
        self.registry = registry
        self.encoder = COEFEncoder(registry)
        self.store = store  # MemberberryStore, optional

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        for span in spans:
            try:
                self._process_span(span)
            except Exception:
                pass  # never crash the tracer pipeline
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True

    def _process_span(self, span: ReadableSpan):
        """Encode one span as a COEF seed and store it."""
        pattern_id = self._match_pattern(span)
        anchors = self._extract_anchors(span, pattern_id)

        # Reconstruct the human-readable content from pattern + anchors
        pattern = self.registry.get(pattern_id)
        content = pattern.template
        for key, value in anchors.items():
            content = content.replace("{{" + key + "}}", value)

        # Encode
        seed = self.encoder.encode(content, pattern_id, anchor_overrides=anchors)

        # Store in DNS
        span_name = span.name or "unknown"
        span_id = format(span.context.span_id, '016x') if span.context else "0"
        self.dns.store(content, name=f"span:{span_name}:{span_id[:8]}")

        # Store seed compact form too
        self.dns.store(seed.to_compact(), name=f"seed:{span_id[:8]}")

        # Store as memberberry memory if store available
        if self.store:
            self._store_as_memory(seed, span_name, anchors)

    def _match_pattern(self, span: ReadableSpan) -> str:
        """Map span name to a pattern ID."""
        name = span.name or ""
        parts = name.split(".")
        # keanu.memory.remember -> memory
        subsystem = parts[1] if len(parts) > 1 else ""
        pattern_map = {
            "memory": "span.memory",
            "pulse": "span.pulse",
            "alive": "span.alive",
            "cli": "span.cli",
        }
        return pattern_map.get(subsystem, "span.generic")

    def _extract_anchors(self, span: ReadableSpan, pattern_id: str) -> dict:
        """Pull span attributes into pattern slots."""
        attrs = {}
        for k, v in (span.attributes or {}).items():
            clean = k.replace("keanu.", "")
            attrs[clean] = str(v)

        # timestamp from span start
        if span.start_time:
            ts = datetime.fromtimestamp(
                span.start_time / 1e9, tz=timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%S")
        else:
            ts = datetime.now().isoformat()
        attrs["timestamp"] = ts

        # fill missing slots with defaults
        pattern = self.registry.get(pattern_id)
        for slot in pattern.slots:
            if slot not in attrs:
                attrs[slot] = ""

        return attrs

    def _store_as_memory(self, seed: Seed, span_name: str, anchors: dict):
        """Store seed as a memberberry memory for searchable recall."""
        from keanu.memory.memberberry import Memory

        subsystem = anchors.get("subsystem", span_name.split(".")[1] if "." in span_name else "trace")
        tags = ["coef", "trace", subsystem]

        self.store.remember(Memory(
            content=seed.to_compact(),
            memory_type="fact",
            tags=tags,
            source="coef_exporter",
            importance=3,
            context=f"pattern:{seed.pattern_id}",
        ))
