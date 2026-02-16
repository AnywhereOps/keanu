"""corrections.py - learning from corrections.

when the human corrects an edit, remember the pattern.
build per-project style preferences over time.
forge new abilities from repeated correction patterns.

in the world: every correction is a lesson. the same mistake twice is a pattern.
the same pattern three times becomes a tool.
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from keanu.paths import keanu_home


_CORRECTIONS_FILE = keanu_home() / "corrections.jsonl"
_STYLE_FILE = keanu_home() / "style_prefs.json"


@dataclass
class Correction:
    """a single correction event."""
    timestamp: float
    file: str
    old_code: str     # what the agent wrote
    new_code: str     # what the human changed it to
    pattern: str = "" # detected pattern category
    context: str = "" # surrounding code or task description

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "file": self.file,
            "old_code": self.old_code,
            "new_code": self.new_code,
            "pattern": self.pattern,
            "context": self.context,
        }


@dataclass
class StylePreference:
    """a learned style preference."""
    rule: str          # what the preference is
    examples: list     # concrete examples
    count: int = 1     # how many times observed
    confidence: float = 0.5

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "examples": self.examples[:5],
            "count": self.count,
            "confidence": self.confidence,
        }


# ============================================================
# CORRECTION LOGGING
# ============================================================

def log_correction(file: str, old_code: str, new_code: str,
                   context: str = "") -> Correction:
    """log a correction event. detects the pattern category."""
    pattern = detect_pattern(old_code, new_code)

    correction = Correction(
        timestamp=time.time(),
        file=file,
        old_code=old_code[:500],
        new_code=new_code[:500],
        pattern=pattern,
        context=context[:200],
    )

    # append to JSONL
    _CORRECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_CORRECTIONS_FILE, "a") as f:
        f.write(json.dumps(correction.to_dict()) + "\n")

    # update style prefs
    if pattern:
        _update_style_pref(pattern, old_code, new_code)

    return correction


def load_corrections(limit: int = 100) -> list[Correction]:
    """load recent corrections from the log."""
    if not _CORRECTIONS_FILE.exists():
        return []

    corrections = []
    try:
        lines = _CORRECTIONS_FILE.read_text().strip().split("\n")
        for line in lines[-limit:]:
            if not line.strip():
                continue
            data = json.loads(line)
            corrections.append(Correction(**data))
    except (json.JSONDecodeError, OSError):
        pass

    return corrections


def correction_patterns(min_count: int = 2) -> dict[str, int]:
    """get correction patterns that have appeared multiple times.

    these are candidates for automatic style rules.
    """
    corrections = load_corrections(limit=500)
    counts: dict[str, int] = {}
    for c in corrections:
        if c.pattern:
            counts[c.pattern] = counts.get(c.pattern, 0) + 1

    return {k: v for k, v in counts.items() if v >= min_count}


# ============================================================
# PATTERN DETECTION
# ============================================================

def detect_pattern(old: str, new: str) -> str:
    """detect what kind of correction was made."""
    old_stripped = old.strip()
    new_stripped = new.strip()

    if not old_stripped or not new_stripped:
        return ""

    # indentation change (check before other patterns since stripped versions match)
    old_indent = len(old) - len(old.lstrip())
    new_indent = len(new) - len(new.lstrip())
    if old_indent != new_indent and old_stripped == new_stripped:
        return "fix_indentation"

    # quote style (only when quotes actually differ)
    if "'" in old_stripped and old_stripped.replace("'", '"') == new_stripped:
        return "prefer_double_quotes"
    if '"' in old_stripped and old_stripped.replace('"', "'") == new_stripped:
        return "prefer_single_quotes"

    # trailing comma (only when comma actually differs)
    if old_stripped + "," == new_stripped:
        return "prefer_trailing_comma"
    if old_stripped.endswith(",") and old_stripped.rstrip(",") == new_stripped:
        return "no_trailing_comma"

    # parentheses style (only when parens with spaces exist)
    if "( " in old_stripped or " )" in old_stripped:
        if old_stripped.replace("( ", "(").replace(" )", ")") == new_stripped:
            return "no_space_in_parens"

    # dict vs dataclass
    if "dict(" in old_stripped and "dataclass" in new_stripped.lower():
        return "prefer_dataclass"
    if "{" in old_stripped and "dataclass" in new_stripped.lower():
        return "prefer_dataclass"

    # type hint additions
    if ": " in new_stripped and ": " not in old_stripped and "=" in old_stripped:
        return "add_type_hints"

    # docstring additions
    if '"""' in new_stripped and '"""' not in old_stripped:
        return "add_docstring"

    # f-string preference
    if ".format(" in old_stripped and "f'" in new_stripped or 'f"' in new_stripped:
        return "prefer_fstring"

    # naming convention
    if _is_camel(old_stripped) and _is_snake(new_stripped):
        return "prefer_snake_case"
    if _is_snake(old_stripped) and _is_camel(new_stripped):
        return "prefer_camel_case"

    # import style
    if old_stripped.startswith("import ") and new_stripped.startswith("from "):
        return "prefer_from_import"
    if old_stripped.startswith("from ") and new_stripped.startswith("import "):
        return "prefer_import"

    return "other"


# ============================================================
# STYLE PREFERENCES
# ============================================================

def load_style_prefs() -> list[StylePreference]:
    """load learned style preferences."""
    if not _STYLE_FILE.exists():
        return []

    try:
        data = json.loads(_STYLE_FILE.read_text())
        return [StylePreference(**p) for p in data]
    except (json.JSONDecodeError, OSError):
        return []


def style_prompt_injection() -> str:
    """generate a prompt injection from learned style preferences.

    high-confidence prefs are injected into the system prompt
    so the agent learns the human's style.
    """
    prefs = load_style_prefs()
    high_conf = [p for p in prefs if p.confidence >= 0.7 and p.count >= 3]

    if not high_conf:
        return ""

    lines = ["Style preferences (learned from corrections):"]
    for p in high_conf[:10]:
        lines.append(f"- {p.rule} (seen {p.count}x)")

    return "\n".join(lines)


def _update_style_pref(pattern: str, old_code: str, new_code: str):
    """update style preferences based on a new correction."""
    prefs = load_style_prefs()

    # find existing pref or create new one
    existing = None
    for p in prefs:
        if p.rule == pattern:
            existing = p
            break

    example = {"old": old_code[:100], "new": new_code[:100]}

    if existing:
        existing.count += 1
        existing.examples.append(example)
        existing.examples = existing.examples[-5:]  # keep last 5
        # confidence grows with repetitions
        existing.confidence = min(0.95, 0.5 + (existing.count * 0.1))
    else:
        prefs.append(StylePreference(
            rule=pattern,
            examples=[example],
            count=1,
            confidence=0.5,
        ))

    _save_style_prefs(prefs)


def _save_style_prefs(prefs: list[StylePreference]):
    """save style preferences."""
    _STYLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = [p.to_dict() for p in prefs]
    _STYLE_FILE.write_text(json.dumps(data, indent=2))


# ============================================================
# HELPERS
# ============================================================

def _is_camel(text: str) -> bool:
    """check if text looks like camelCase."""
    import re
    return bool(re.search(r'[a-z][A-Z]', text))


def _is_snake(text: str) -> bool:
    """check if text looks like snake_case."""
    import re
    return bool(re.search(r'[a-z]_[a-z]', text))
