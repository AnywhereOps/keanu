#!/usr/bin/env python3
"""
COEF Codec Demo
Send the barcode, not the color name.
"""

from keanu.compress.codec import (
    PatternRegistry, COEFEncoder, COEFDecoder,
    Seed, BUILTIN_PATTERNS,
)


def demo():
    print("=" * 60)
    print("COEF LOSSLESS DEMO")
    print("Send the barcode, not the color name.")
    print("=" * 60)

    registry = PatternRegistry()
    for p in BUILTIN_PATTERNS:
        registry.register(p)

    encoder = COEFEncoder(registry)
    decoder = COEFDecoder(registry)

    # --- Example 1: Python function ---
    original = 'def greet(name):\n    """Say hello."""\n    return f"hello {name}"'

    print(f"\n[ORIGINAL] {len(original)} chars")
    print(original + "\n")

    seed = encoder.encode(content=original, pattern_id="python_function")
    compact = seed.to_compact()
    print(f"[SEED] {len(compact)} chars")
    print(f"  {compact}")
    print(f"  Compression: {len(original)} -> {len(compact)} ({len(original)/len(compact):.1f}x)\n")

    result = decoder.decode(seed)
    print(f"[VERIFY] Lossless: {result.is_lossless}")
    print(f"  Hash match: {result.content_hash[:16]} == {result.expected_hash[:16]}")
    print()

    # --- Example 2: Color reading ---
    print("-" * 60)
    reading = "[helix@README.md] 🌅 sunrise R:+7 Y:+6 B:+8 wise:9.2"
    reading_seed = encoder.encode(
        content=reading, pattern_id="color_reading",
        anchor_overrides={
            "source": "helix@README.md", "symbol": "🌅", "state": "sunrise",
            "red": "+7", "yellow": "+6", "blue": "+8", "wise": "9.2",
        },
    )
    reading_result = decoder.decode(reading_seed)
    print(f"[COLOR]  Original:  {reading} ({len(reading)} chars)")
    print(f"         Seed:      {reading_seed.to_compact()} ({len(reading_seed.to_compact())} chars)")
    print(f"         Decoded:   {reading_result.content}")
    print(f"         Lossless:  {reading_result.is_lossless}\n")

    # --- Example 3: Signal message ---
    print("-" * 60)
    sig = "[drew@keanu] scan complete -> ship"
    sig_seed = encoder.encode(
        content=sig, pattern_id="signal_message",
        anchor_overrides={
            "sender": "drew", "context": "keanu",
            "signal": "scan complete", "action": "ship",
        },
    )
    sig_result = decoder.decode(sig_seed)
    print(f"[SIGNAL] Original:  {sig} ({len(sig)} chars)")
    print(f"         Seed:      {sig_seed.to_compact()} ({len(sig_seed.to_compact())} chars)")
    print(f"         Decoded:   {sig_result.content}")
    print(f"         Lossless:  {sig_result.is_lossless}\n")

    # --- Example 4: Round-trip ---
    print("-" * 60)
    print("[ROUND-TRIP] Serialize -> Transmit -> Reconstruct")
    reconstructed = Seed.from_compact(compact)
    print(f"  Pattern: {reconstructed.pattern_id}")
    print(f"  Anchors: {len(reconstructed.anchors)}")
    print(f"  Hash prefix preserved: {reconstructed.content_hash}")
    print()

    # --- Pattern catalog ---
    print("=" * 60)
    print("PATTERN REGISTRY")
    print("=" * 60)
    for pid in registry.list_patterns():
        p = registry.get(pid)
        print(f"  {pid}: {p.description}")
        print(f"    slots: {p.slots}")

    print(f"\nTotal patterns: {len(registry.list_patterns())}")
    print("Training = committing more patterns.")


if __name__ == "__main__":
    demo()
