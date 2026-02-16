"""mistakes.py - every error the agent makes gets logged with context.

before acting, the agent can check: "have I made this mistake before?"
mistake patterns become lint rules, then abilities, then ash.
the agent gets smarter by failing, not just by succeeding.

different from miss_tracker (router fallthroughs). this tracks execution
errors: failed edits, broken tests, bad commands, wrong assumptions.

in the world: scars that teach. the ledger of what went wrong and why.
"""

import time
from collections import Counter
from pathlib import Path

from keanu.paths import MISTAKES_FILE
from keanu.io import read_jsonl, append_jsonl

# how many days before a mistake is considered stale
DECAY_DAYS = 30


def log_mistake(action: str, args: dict, error: str,
                context: str = "", category: str = ""):
    """record a mistake. called when an ability execution fails.

    action: the ability that failed (edit, run, write, etc.)
    args: the args that were passed
    error: the error message
    context: what the agent was trying to do
    category: optional classification (syntax, path, logic, timeout, etc.)
    """
    record = {
        "ts": int(time.time()),
        "action": action,
        "args_summary": _summarize_args(args),
        "error": error[:500],
        "context": context[:200],
        "category": category or _classify(action, error),
    }
    append_jsonl(MISTAKES_FILE, record)


def check_before(action: str, args: dict) -> list[dict]:
    """check if we've made a similar mistake before.

    returns relevant past mistakes sorted by recency.
    the agent should call this before executing risky actions.
    """
    mistakes = _load_active()
    relevant = []

    for m in mistakes:
        if m["action"] != action:
            continue
        # same action + similar args = worth surfacing
        if _args_overlap(m["args_summary"], _summarize_args(args)):
            relevant.append(m)

    # most recent first
    return sorted(relevant, key=lambda m: m["ts"], reverse=True)[:5]


def get_patterns(limit: int = 20) -> list[dict]:
    """find recurring mistake patterns.

    groups by (action, category) and counts. returns patterns sorted
    by frequency. patterns that repeat 3+ times are forge candidates.
    """
    mistakes = _load_active()
    if not mistakes:
        return []

    counts = Counter()
    examples = {}

    for m in mistakes:
        key = (m["action"], m["category"])
        counts[key] += 1
        # keep the most recent example
        if key not in examples or m["ts"] > examples[key]["ts"]:
            examples[key] = m

    patterns = []
    for (action, category), count in counts.most_common(limit):
        patterns.append({
            "action": action,
            "category": category,
            "count": count,
            "forgeable": count >= 3,
            "latest_error": examples[(action, category)]["error"],
            "latest_ts": examples[(action, category)]["ts"],
        })

    return patterns


def get_mistakes(limit: int = 50) -> list[dict]:
    """read recent mistakes."""
    return _load_active()[-limit:]


def clear_stale():
    """remove mistakes older than DECAY_DAYS. called periodically."""
    cutoff = int(time.time()) - (DECAY_DAYS * 86400)
    all_mistakes = read_jsonl(MISTAKES_FILE)
    active = [m for m in all_mistakes if m.get("ts", 0) > cutoff]

    if len(active) < len(all_mistakes):
        # rewrite the file with only active mistakes
        if MISTAKES_FILE.exists():
            MISTAKES_FILE.write_text("")
        for m in active:
            append_jsonl(MISTAKES_FILE, m)

    return len(all_mistakes) - len(active)


def stats() -> dict:
    """summary stats for the mistake ledger."""
    all_m = read_jsonl(MISTAKES_FILE)
    active = _filter_active(all_m)
    categories = Counter(m.get("category", "unknown") for m in active)
    actions = Counter(m.get("action", "unknown") for m in active)

    return {
        "total": len(all_m),
        "active": len(active),
        "stale": len(all_m) - len(active),
        "by_category": dict(categories.most_common(10)),
        "by_action": dict(actions.most_common(10)),
        "patterns_forgeable": sum(1 for p in get_patterns() if p["forgeable"]),
    }


# ============================================================
# INTERNALS
# ============================================================

def _load_active() -> list[dict]:
    """load mistakes that haven't decayed."""
    return _filter_active(read_jsonl(MISTAKES_FILE))


def _filter_active(mistakes: list[dict]) -> list[dict]:
    """filter out stale mistakes."""
    cutoff = int(time.time()) - (DECAY_DAYS * 86400)
    return [m for m in mistakes if m.get("ts", 0) > cutoff]


def _summarize_args(args: dict) -> str:
    """compact summary of args for comparison."""
    if not args:
        return ""
    parts = []
    for k, v in sorted(args.items()):
        v_str = str(v)[:50]
        parts.append(f"{k}={v_str}")
    return "|".join(parts)


def _args_overlap(summary_a: str, summary_b: str) -> bool:
    """check if two arg summaries share key tokens."""
    if not summary_a or not summary_b:
        return False
    tokens_a = set(summary_a.lower().split("|"))
    tokens_b = set(summary_b.lower().split("|"))
    return bool(tokens_a & tokens_b)


def _classify(action: str, error: str) -> str:
    """auto-classify a mistake from the error message."""
    err = error.lower()

    if "not unique" in err or "found 2 times" in err or "found 3 times" in err:
        return "ambiguous_edit"
    if "not found in" in err:
        return "stale_reference"
    if "not found" in err or "no such file" in err:
        return "path"
    if "permission" in err or "access denied" in err:
        return "permission"
    if "timeout" in err or "timed out" in err:
        return "timeout"
    if "syntax" in err or "invalid syntax" in err:
        return "syntax"
    if "import" in err or "module" in err:
        return "import"
    if "blocked" in err:
        return "safety"
    if "assert" in err or "fail" in err:
        return "test_failure"
    if "type" in err and "error" in err:
        return "type"

    return "unknown"
