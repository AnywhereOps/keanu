"""forge: scaffold new abilities from the miss log.

miss -> see what's needed -> scaffold -> implement -> test -> register.
each new ability improves router coverage, revealing new gaps.
the flywheel IS convergence applied to the system itself.
"""

from pathlib import Path

from keanu.abilities.miss_tracker import analyze_misses, get_misses

# where abilities and tests live
ABILITIES_DIR = Path(__file__).parent
TESTS_DIR = ABILITIES_DIR.parent.parent.parent / "tests"

ABILITY_TEMPLATE = '''\
"""{name}: {description}"""

from keanu.abilities import Ability, ability


@ability
class {class_name}Ability(Ability):

    name = "{name}"
    description = "{description}"
    keywords = [{keywords_str}]

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        p = prompt.lower()

        # exact phrase matches (high confidence)
        if any(phrase in p for phrase in self.keywords[:3]):
            return True, 0.9

        # single keyword matches
        if any(kw in p for kw in self.keywords):
            return True, 0.7

        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        # TODO: implement {name}
        return {{
            "success": True,
            "result": "{name} executed (stub)",
            "data": {{}},
        }}
'''

TEST_TEMPLATE = '''\
"""Tests for {name} ability."""

import pytest
from keanu.abilities import find_ability, _REGISTRY


class Test{class_name}Ability:

    def test_registered(self):
        assert "{name}" in _REGISTRY

    def test_can_handle_keyword(self):
        ab = _REGISTRY["{name}"]
        can, conf = ab.can_handle("{first_keyword}")
        assert can
        assert conf >= 0.7

    def test_execute_stub(self):
        ab = _REGISTRY["{name}"]
        result = ab.execute("test prompt")
        assert result["success"]
'''


def forge_ability(name: str, description: str, keywords: list[str]) -> dict:
    """Scaffold a new ability + test from templates.

    Returns dict with paths of created files.
    """
    # sanitize
    name = name.strip().lower().replace(" ", "_").replace("-", "_")
    class_name = "".join(w.capitalize() for w in name.split("_"))
    keywords_str = ", ".join(f'"{kw.strip()}"' for kw in keywords if kw.strip())
    first_keyword = keywords[0].strip() if keywords else name

    ability_file = ABILITIES_DIR / f"{name}.py"
    test_file = TESTS_DIR / f"test_{name}_ability.py"

    if ability_file.exists():
        return {"error": f"{ability_file} already exists"}

    ability_code = ABILITY_TEMPLATE.format(
        name=name,
        description=description,
        class_name=class_name,
        keywords_str=keywords_str,
        first_keyword=first_keyword,
    )

    test_code = TEST_TEMPLATE.format(
        name=name,
        class_name=class_name,
        first_keyword=first_keyword,
    )

    ability_file.write_text(ability_code)
    test_file.write_text(test_code)

    return {
        "ability_file": str(ability_file),
        "test_file": str(test_file),
        "name": name,
        "class_name": class_name,
    }


def suggest_from_misses(limit: int = 50) -> list[dict]:
    """Analyze miss log and suggest potential abilities.

    Returns list of {word, count} sorted by frequency.
    """
    analysis = analyze_misses(limit)
    misses = get_misses(limit)
    total = len(misses)

    suggestions = []
    for word, count in analysis:
        suggestions.append({
            "word": word,
            "count": count,
            "pct": round(count / total * 100) if total else 0,
        })

    return suggestions
