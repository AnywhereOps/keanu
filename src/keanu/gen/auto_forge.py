"""auto_forge.py - miss-to-ability pipeline.

every router miss, every failed edit, every test failure is a signal.
when a pattern repeats 3+ times, auto-suggest (or auto-build) a new ability.
the system builds its own action bar from its own failures.

in the world: the forge flywheel. every miss becomes a tool.
the system literally builds itself.
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from keanu.paths import keanu_home


_FORGE_LOG = keanu_home() / "forge_log.jsonl"


@dataclass
class ForgeCandidate:
    """a candidate ability to be forged."""
    name: str
    description: str
    keywords: list[str]
    miss_count: int
    examples: list[str]     # example prompts that triggered the miss
    confidence: float = 0.0
    auto_forgeable: bool = False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "keywords": self.keywords,
            "miss_count": self.miss_count,
            "examples": self.examples[:5],
            "confidence": self.confidence,
            "auto_forgeable": self.auto_forgeable,
        }


@dataclass
class ForgeResult:
    """result of an auto-forge operation."""
    success: bool
    ability_name: str = ""
    ability_file: str = ""
    test_file: str = ""
    errors: list[str] = field(default_factory=list)


# ============================================================
# MISS ANALYSIS
# ============================================================

def analyze_misses(min_count: int = 3) -> list[ForgeCandidate]:
    """analyze router misses and identify forge candidates.

    reads the miss log, clusters by keywords, identifies patterns
    that have repeated enough to warrant a new ability.
    """
    try:
        from keanu.abilities.miss_tracker import get_misses
    except ImportError:
        return []

    misses = get_misses(limit=500)
    if not misses:
        return []

    # cluster misses by extracting key actions/topics
    clusters: dict[str, list[dict]] = {}
    for miss in misses:
        prompt = miss.get("prompt", "")
        key = _extract_action(prompt)
        if key:
            clusters.setdefault(key, []).append(miss)

    candidates = []
    for key, items in clusters.items():
        if len(items) < min_count:
            continue

        examples = [m.get("prompt", "")[:100] for m in items[:5]]
        keywords = _extract_keywords(examples)

        candidate = ForgeCandidate(
            name=key,
            description=f"handle '{key}' requests ({len(items)} misses)",
            keywords=keywords,
            miss_count=len(items),
            examples=examples,
            confidence=min(0.95, 0.5 + (len(items) * 0.05)),
            auto_forgeable=len(items) >= 5,
        )
        candidates.append(candidate)

    # sort by miss count
    candidates.sort(key=lambda c: -c.miss_count)
    return candidates


def analyze_mistakes(min_count: int = 3) -> list[ForgeCandidate]:
    """analyze mistake patterns and identify forge candidates.

    reads the mistake log, looks for patterns that keep repeating.
    if an agent keeps making the same kind of mistake, there should
    be an ability that handles it.
    """
    try:
        from keanu.abilities.world.mistakes import get_patterns
    except ImportError:
        return []

    patterns = get_patterns()
    candidates = []

    for p in patterns:
        if p.get("count", 0) < min_count:
            continue
        if not p.get("forgeable", False):
            continue

        candidate = ForgeCandidate(
            name=f"fix_{p['category']}",
            description=f"auto-fix {p['category']} errors in {p['action']}",
            keywords=[p["category"], p["action"], "fix", "auto"],
            miss_count=p["count"],
            examples=[p.get("latest_error", "")[:100]],
            confidence=min(0.95, 0.5 + (p["count"] * 0.05)),
            auto_forgeable=p["count"] >= 5,
        )
        candidates.append(candidate)

    candidates.sort(key=lambda c: -c.miss_count)
    return candidates


def get_all_candidates(min_count: int = 3) -> list[ForgeCandidate]:
    """get all forge candidates from both misses and mistakes."""
    candidates = analyze_misses(min_count) + analyze_mistakes(min_count)
    # deduplicate by name
    seen = set()
    unique = []
    for c in candidates:
        if c.name not in seen:
            seen.add(c.name)
            unique.append(c)
    return sorted(unique, key=lambda c: -c.miss_count)


# ============================================================
# AUTO-FORGE
# ============================================================

def auto_forge(candidate: ForgeCandidate) -> ForgeResult:
    """automatically scaffold a new ability from a forge candidate.

    uses the forge module to create the ability file and test file.
    the ability starts as a stub (returns not-implemented), but the
    scaffold has all the right metadata.
    """
    try:
        from keanu.abilities.forge import forge_ability
    except ImportError:
        return ForgeResult(success=False, errors=["forge module not available"])

    result = forge_ability(
        candidate.name,
        candidate.description,
        candidate.keywords,
    )

    if "error" in result:
        return ForgeResult(success=False, errors=[result["error"]])

    # log the forge event
    _log_forge(candidate)

    return ForgeResult(
        success=True,
        ability_name=candidate.name,
        ability_file=result.get("ability_file", ""),
        test_file=result.get("test_file", ""),
    )


def auto_forge_all(min_count: int = 5, dry_run: bool = True) -> list[dict]:
    """find all auto-forgeable candidates and forge them.

    dry_run=True (default) just reports what would be forged.
    dry_run=False actually creates the files.
    """
    candidates = get_all_candidates(min_count)
    forgeable = [c for c in candidates if c.auto_forgeable]

    results = []
    for c in forgeable:
        if dry_run:
            results.append({
                "action": "would_forge",
                "candidate": c.to_dict(),
            })
        else:
            result = auto_forge(c)
            results.append({
                "action": "forged" if result.success else "failed",
                "candidate": c.to_dict(),
                "result": {
                    "ability_file": result.ability_file,
                    "test_file": result.test_file,
                    "errors": result.errors,
                },
            })

    return results


# ============================================================
# FORGE LOG
# ============================================================

def _log_forge(candidate: ForgeCandidate):
    """log a forge event."""
    _FORGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": time.time(),
        "name": candidate.name,
        "miss_count": candidate.miss_count,
        "confidence": candidate.confidence,
    }
    with open(_FORGE_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def forge_history(limit: int = 50) -> list[dict]:
    """get recent forge history."""
    if not _FORGE_LOG.exists():
        return []

    entries = []
    try:
        for line in _FORGE_LOG.read_text().strip().split("\n"):
            if line.strip():
                entries.append(json.loads(line))
    except (json.JSONDecodeError, OSError):
        pass

    return entries[-limit:]


# ============================================================
# PROACTIVE OPS
# ============================================================

def check_project_health(root: str = ".") -> dict:
    """check project health proactively. no LLM needed.

    looks for: stale dependencies, missing tests, lint issues,
    unused code, documentation gaps.
    """
    health = {
        "issues": [],
        "score": 100,  # start at 100, subtract for issues
    }

    # check for missing tests
    try:
        from keanu.analysis.suggestions import check_missing_tests
        missing = check_missing_tests(root)
        if missing:
            health["issues"].append({
                "category": "missing_tests",
                "count": len(missing),
                "message": f"{len(missing)} source files without tests",
                "severity": "warning",
            })
            health["score"] -= min(20, len(missing) * 2)
    except Exception:
        pass

    # check for code suggestions
    try:
        from keanu.analysis.suggestions import scan_directory
        report = scan_directory(root, max_files=50)
        if report.count > 0:
            cats = report.by_category()
            for cat, items in cats.items():
                if len(items) >= 3:
                    health["issues"].append({
                        "category": cat,
                        "count": len(items),
                        "message": f"{len(items)} {cat} issues",
                        "severity": "info",
                    })
                    health["score"] -= min(10, len(items))
    except Exception:
        pass

    # check for router misses
    try:
        from keanu.abilities.miss_tracker import get_misses
        misses = get_misses(limit=100)
        if len(misses) > 10:
            health["issues"].append({
                "category": "router_misses",
                "count": len(misses),
                "message": f"{len(misses)} router misses (consider forging abilities)",
                "severity": "hint",
            })
    except Exception:
        pass

    # check for mistake patterns
    try:
        from keanu.abilities.world.mistakes import get_patterns
        forgeable = [p for p in get_patterns() if p.get("forgeable")]
        if forgeable:
            health["issues"].append({
                "category": "forgeable_mistakes",
                "count": len(forgeable),
                "message": f"{len(forgeable)} mistake patterns ready to forge",
                "severity": "hint",
            })
    except Exception:
        pass

    health["score"] = max(0, health["score"])
    return health


# ============================================================
# HELPERS
# ============================================================

def _extract_action(prompt: str) -> str:
    """extract the core action from a prompt."""
    words = prompt.lower().split()[:5]
    # look for verb-noun patterns
    verbs = {"create", "build", "make", "generate", "run", "deploy",
             "test", "check", "validate", "convert", "transform",
             "parse", "format", "send", "fetch", "upload", "download"}

    skip = {"the", "a", "an", "this", "that", "my", "our", "your"}
    for i, word in enumerate(words):
        if word in verbs:
            # find next meaningful word after verb
            for j in range(i + 1, len(words)):
                if words[j] not in skip:
                    return f"{word}_{words[j]}"

    # fallback: first two meaningful words
    meaningful = [w for w in words if len(w) > 3 and w not in {"the", "this", "that", "with"}]
    if len(meaningful) >= 2:
        return f"{meaningful[0]}_{meaningful[1]}"
    if meaningful:
        return meaningful[0]
    return ""


def _extract_keywords(examples: list[str]) -> list[str]:
    """extract common keywords from example prompts."""
    word_counts: dict[str, int] = {}
    stop_words = {"the", "a", "an", "is", "are", "was", "to", "for", "in", "on",
                  "of", "and", "or", "but", "not", "it", "this", "that", "with",
                  "from", "by", "at", "be", "do", "can", "how", "what", "when"}

    for example in examples:
        words = set(example.lower().split())
        for word in words:
            clean = word.strip(".,!?\"'()[]{}:")
            if clean and len(clean) > 2 and clean not in stop_words:
                word_counts[clean] = word_counts.get(clean, 0) + 1

    # top keywords that appear in multiple examples
    sorted_words = sorted(word_counts.items(), key=lambda x: -x[1])
    return [w for w, c in sorted_words[:5] if c >= 2] or [w for w, _ in sorted_words[:3]]
