"""Tests for the forge flywheel: miss tracking + ability scaffolding."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from keanu.abilities.miss_tracker import (
    log_miss, get_misses, analyze_misses, clear_misses, MISS_FILE,
)
from keanu.abilities.forge import forge_ability, suggest_from_misses


@pytest.fixture(autouse=True)
def clean_misses(tmp_path):
    """Redirect miss file to tmp for all tests."""
    test_file = tmp_path / "misses.jsonl"
    with patch("keanu.abilities.miss_tracker.MISS_FILE", test_file):
        with patch("keanu.abilities.forge.get_misses",
                   side_effect=lambda limit=50: _read_jsonl(test_file, limit)):
            with patch("keanu.abilities.forge.analyze_misses",
                       side_effect=lambda limit=50: _analyze(test_file, limit)):
                yield test_file


def _read_jsonl(path, limit):
    if not path.exists():
        return []
    lines = path.read_text().strip().splitlines()
    results = []
    for line in lines[-limit:]:
        try:
            results.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return results


def _analyze(path, limit):
    from collections import Counter
    misses = _read_jsonl(path, limit)
    noise = {"the", "a", "an", "is", "it", "to", "and", "or", "of", "in",
             "on", "for", "my", "me", "i", "do", "can", "you", "this", "that",
             "how", "what", "please", "just", "with", "from"}
    words = Counter()
    for m in misses:
        tokens = m["prompt"].lower().split()
        for t in tokens:
            t = t.strip(".,!?\"'()[]")
            if len(t) > 2 and t not in noise:
                words[t] += 1
    return words.most_common(20)


# ============================================================
# MISS TRACKER
# ============================================================

class TestMissTracker:

    def test_log_and_get(self, clean_misses):
        log_miss("explain how scan works", 0.3)
        log_miss("what does converge do", 0.2)
        misses = get_misses()
        assert len(misses) == 2
        assert misses[0]["prompt"] == "explain how scan works"
        assert misses[0]["best_confidence"] == 0.3

    def test_get_empty(self, clean_misses):
        assert get_misses() == []

    def test_analyze(self, clean_misses):
        for _ in range(5):
            log_miss("explain how scan works", 0.3)
        for _ in range(3):
            log_miss("explain the converge engine", 0.2)
        analysis = analyze_misses()
        words = dict(analysis)
        assert "explain" in words
        assert words["explain"] == 8

    def test_clear(self, clean_misses):
        log_miss("test", 0.1)
        assert len(get_misses()) == 1
        clear_misses()
        assert len(get_misses()) == 0


# ============================================================
# FORGE
# ============================================================

class TestForge:

    def test_scaffold_creates_files(self, tmp_path):
        with patch("keanu.abilities.forge.ABILITIES_DIR", tmp_path):
            with patch("keanu.abilities.forge.TESTS_DIR", tmp_path):
                result = forge_ability("explain", "Contextual help", ["explain", "how does"])
                assert "error" not in result
                assert (tmp_path / "explain.py").exists()
                assert (tmp_path / "test_explain_ability.py").exists()

    def test_scaffold_content(self, tmp_path):
        with patch("keanu.abilities.forge.ABILITIES_DIR", tmp_path):
            with patch("keanu.abilities.forge.TESTS_DIR", tmp_path):
                forge_ability("explain", "Contextual help", ["explain", "how does"])
                code = (tmp_path / "explain.py").read_text()
                assert "class ExplainAbility" in code
                assert '@ability' in code
                assert 'name = "explain"' in code

    def test_scaffold_refuses_duplicate(self, tmp_path):
        with patch("keanu.abilities.forge.ABILITIES_DIR", tmp_path):
            with patch("keanu.abilities.forge.TESTS_DIR", tmp_path):
                forge_ability("explain", "Contextual help", ["explain"])
                result = forge_ability("explain", "Contextual help", ["explain"])
                assert "error" in result

    def test_suggest_from_misses(self, clean_misses):
        for _ in range(5):
            log_miss("explain how scan works", 0.3)
        suggestions = suggest_from_misses()
        assert len(suggestions) > 0
        words = [s["word"] for s in suggestions]
        assert "explain" in words


# ============================================================
# ROUTER INTEGRATION
# ============================================================

class TestRouterMissLogging:

    def test_router_logs_miss_on_fallthrough(self, clean_misses):
        """When router falls through to LLM, a miss should be logged."""
        from keanu.abilities.router import AbilityRouter

        router = AbilityRouter()
        with patch.object(router, "_call_oracle") as mock_llm:
            mock_llm.return_value = type("R", (), {
                "source": "claude", "response": "ok"
            })()
            router.route("something no ability handles")

        misses = get_misses()
        assert len(misses) == 1
        assert "something no ability handles" in misses[0]["prompt"]
