"""miss_tracker: captures router fallthroughs.

every time the router falls through to Claude, that's a signal
an ability should exist. this captures those misses so forge
can suggest what to build next.
"""

import time
from collections import Counter

from keanu.paths import MISS_FILE
from keanu.io import append_jsonl, read_jsonl


def log_miss(prompt: str, confidence: float = 0.0):
    """Append a miss to the log."""
    append_jsonl(MISS_FILE, {
        "ts": int(time.time()),
        "prompt": prompt[:500],
        "best_confidence": round(confidence, 3),
    })


def get_misses(limit: int = 50) -> list[dict]:
    """Read recent misses."""
    all_misses = read_jsonl(MISS_FILE)
    return all_misses[-limit:]


def analyze_misses(limit: int = 50) -> list[tuple[str, int]]:
    """Group misses by common words, return (word, count) sorted by frequency."""
    misses = get_misses(limit)
    if not misses:
        return []

    # skip noise words
    noise = {
        "the", "a", "an", "is", "it", "to", "and", "or", "of", "in",
        "on", "for", "my", "me", "i", "do", "can", "you", "this", "that",
        "how", "what", "please", "just", "with", "from",
    }

    words = Counter()
    for m in misses:
        tokens = m["prompt"].lower().split()
        for t in tokens:
            t = t.strip(".,!?\"'()[]")
            if len(t) > 2 and t not in noise:
                words[t] += 1

    return words.most_common(20)


def clear_misses():
    """Truncate the miss log."""
    if MISS_FILE.exists():  # noqa: keep direct Path usage for truncate
        MISS_FILE.write_text("")
