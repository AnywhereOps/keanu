"""miss_tracker: captures router fallthroughs.

every time the router falls through to Claude, that's a signal
an ability should exist. this captures those misses so forge
can suggest what to build next.
"""

import json
import time
from collections import Counter
from pathlib import Path

MISS_FILE = Path.home() / ".keanu" / "misses.jsonl"


def log_miss(prompt: str, confidence: float = 0.0):
    """Append a miss to the log."""
    MISS_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": int(time.time()),
        "prompt": prompt[:500],
        "best_confidence": round(confidence, 3),
    }
    with open(MISS_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def get_misses(limit: int = 50) -> list[dict]:
    """Read recent misses."""
    if not MISS_FILE.exists():
        return []
    lines = MISS_FILE.read_text().strip().splitlines()
    misses = []
    for line in lines[-limit:]:
        try:
            misses.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return misses


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
    if MISS_FILE.exists():
        MISS_FILE.write_text("")
