"""metrics.py - convergence metrics. tracks fire vs ash over time.

the goal: the ratio of fire (LLM calls) to ash (ability executions)
should shift toward ash over time. every miss that gets forged into
an ability moves the needle. this module tracks that movement.

in the world: the thermometer. how much of the work is converged?
"""

import time
from collections import Counter
from pathlib import Path

from keanu.paths import METRICS_FILE
from keanu.io import read_jsonl, append_jsonl


# ============================================================
# RECORDING
# ============================================================

def record_fire(prompt_summary: str = "", legend: str = "", model: str = "",
                tokens: int = 0):
    """record an oracle (fire) call."""
    append_jsonl(METRICS_FILE, {
        "ts": int(time.time()),
        "type": "fire",
        "prompt_summary": prompt_summary[:100],
        "legend": legend,
        "model": model,
        "tokens": tokens,
    })


def record_ash(ability_name: str, success: bool = True):
    """record an ability (ash) execution."""
    append_jsonl(METRICS_FILE, {
        "ts": int(time.time()),
        "type": "ash",
        "ability": ability_name,
        "success": success,
    })


def record_forge(ability_name: str):
    """record a new ability being forged (a convergence event)."""
    append_jsonl(METRICS_FILE, {
        "ts": int(time.time()),
        "type": "forge",
        "ability": ability_name,
    })


# ============================================================
# ANALYSIS
# ============================================================

def ratio(days: int = 7) -> dict:
    """fire-to-ash ratio over a time window.

    returns {fire, ash, ratio, trend}
    ratio = ash / (fire + ash). 1.0 = pure efficiency. 0.0 = pure fire.
    """
    cutoff = int(time.time()) - (days * 86400)
    records = [r for r in read_jsonl(METRICS_FILE) if r.get("ts", 0) > cutoff]

    fire = sum(1 for r in records if r.get("type") == "fire")
    ash = sum(1 for r in records if r.get("type") == "ash")
    total = fire + ash

    current_ratio = ash / total if total > 0 else 0.0

    # compare to previous period for trend
    prev_cutoff = cutoff - (days * 86400)
    prev_records = [r for r in read_jsonl(METRICS_FILE)
                    if prev_cutoff < r.get("ts", 0) <= cutoff]
    prev_fire = sum(1 for r in prev_records if r.get("type") == "fire")
    prev_ash = sum(1 for r in prev_records if r.get("type") == "ash")
    prev_total = prev_fire + prev_ash
    prev_ratio = prev_ash / prev_total if prev_total > 0 else 0.0

    if total == 0:
        trend = "no data"
    elif prev_total == 0:
        trend = "first period"
    elif current_ratio > prev_ratio + 0.05:
        trend = "converging"
    elif current_ratio < prev_ratio - 0.05:
        trend = "diverging"
    else:
        trend = "stable"

    return {
        "fire": fire,
        "ash": ash,
        "total": total,
        "ratio": round(current_ratio, 3),
        "prev_ratio": round(prev_ratio, 3),
        "trend": trend,
        "days": days,
    }


def by_ability(days: int = 7) -> list[dict]:
    """breakdown of ash usage by ability."""
    cutoff = int(time.time()) - (days * 86400)
    records = [r for r in read_jsonl(METRICS_FILE)
               if r.get("ts", 0) > cutoff and r.get("type") == "ash"]

    counts = Counter()
    successes = Counter()
    for r in records:
        name = r.get("ability", "unknown")
        counts[name] += 1
        if r.get("success", True):
            successes[name] += 1

    result = []
    for name, count in counts.most_common(20):
        result.append({
            "ability": name,
            "count": count,
            "success_rate": round(successes[name] / count, 2) if count > 0 else 0,
        })
    return result


def by_legend(days: int = 7) -> list[dict]:
    """breakdown of fire usage by legend."""
    cutoff = int(time.time()) - (days * 86400)
    records = [r for r in read_jsonl(METRICS_FILE)
               if r.get("ts", 0) > cutoff and r.get("type") == "fire"]

    counts = Counter()
    tokens = Counter()
    for r in records:
        legend = r.get("legend", "unknown")
        counts[legend] += 1
        tokens[legend] += r.get("tokens", 0)

    result = []
    for legend, count in counts.most_common(10):
        result.append({
            "legend": legend,
            "calls": count,
            "total_tokens": tokens[legend],
        })
    return result


def forges(days: int = 30) -> list[dict]:
    """list of abilities forged in the time window."""
    cutoff = int(time.time()) - (days * 86400)
    records = [r for r in read_jsonl(METRICS_FILE)
               if r.get("ts", 0) > cutoff and r.get("type") == "forge"]
    return records


def dashboard(days: int = 7) -> dict:
    """full convergence dashboard."""
    r = ratio(days)
    return {
        "period_days": days,
        "fire_ash_ratio": r,
        "by_ability": by_ability(days),
        "by_legend": by_legend(days),
        "forges_30d": len(forges(30)),
        "message": _dashboard_message(r),
    }


def _dashboard_message(r: dict) -> str:
    """human-readable summary of convergence state."""
    if r["total"] == 0:
        return "no data yet. start using keanu and the metrics will appear."

    pct = int(r["ratio"] * 100)

    if r["trend"] == "converging":
        return f"{pct}% ash (up from {int(r['prev_ratio'] * 100)}%). converging."
    elif r["trend"] == "diverging":
        return f"{pct}% ash (down from {int(r['prev_ratio'] * 100)}%). more fire than before. check misses."
    elif r["trend"] == "stable":
        return f"{pct}% ash. stable. forge more abilities to push the ratio."
    else:
        return f"{pct}% ash. {r['fire']} fire calls, {r['ash']} ability executions."
