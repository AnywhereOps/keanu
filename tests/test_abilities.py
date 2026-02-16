"""Tests for the abilities module: protocol, registry, router, action bar."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from keanu.abilities import (
    Ability, ability, find_ability, list_abilities, _REGISTRY,
    record_cast, get_grimoire, _load_grimoire, _save_grimoire, GRIMOIRE,
)
from keanu.abilities.router import AbilityRouter, RouteResult


# ============================================================
# REGISTRY
# ============================================================

class TestRegistry:

    def test_all_abilities_registered(self):
        """The full action bar + hands should be in the registry."""
        names = set(_REGISTRY.keys())
        action_bar = {
            "scout", "recall", "scry", "attune", "purge",
            "soulstone", "inspect", "recount", "explore", "fuse",
        }
        hands = {"read", "write", "edit", "search", "ls", "run", "git", "test", "lint", "format", "patch"}
        expected = action_bar | hands
        assert expected.issubset(names), f"Missing: {expected - names}"

    def test_list_abilities(self):
        abilities = list_abilities()
        assert len(abilities) >= 15
        names = [a["name"] for a in abilities]
        assert "scout" in names
        assert "recall" in names
        assert "soulstone" in names

    def test_each_ability_has_required_fields(self):
        for ab in _REGISTRY.values():
            assert ab.name, f"Ability missing name: {ab}"
            assert ab.description, f"{ab.name} missing description"
            assert isinstance(ab.keywords, list), f"{ab.name} keywords not a list"
            assert len(ab.keywords) > 0, f"{ab.name} has no keywords"


# ============================================================
# FIND ABILITY (routing)
# ============================================================

class TestFindAbility:

    def test_scout_matches(self):
        ab, conf = find_ability("generate todo for the project")
        assert ab is not None
        assert ab.name == "scout"
        assert conf >= 0.8

    def test_recall_matches(self):
        ab, conf = find_ability("what did i decide about deployment?")
        assert ab is not None
        assert ab.name == "recall"
        assert conf >= 0.8

    def test_scry_matches_pattern_name(self):
        ab, conf = find_ability("detect empathy_frustrated in this")
        assert ab is not None
        assert ab.name == "scry"
        assert conf >= 0.8

    def test_attune_matches_helix(self):
        ab, conf = find_ability("helix scan this document")
        assert ab is not None
        assert ab.name == "attune"
        assert conf >= 0.8

    def test_purge_matches_alive_check(self):
        ab, conf = find_ability("is this text alive or grey")
        assert ab is not None
        assert ab.name == "purge"
        assert conf >= 0.8

    def test_soulstone_matches_compress(self):
        ab, conf = find_ability("compress this module")
        assert ab is not None
        assert ab.name == "soulstone"
        assert conf >= 0.8

    def test_inspect_matches_health(self):
        ab, conf = find_ability("health check")
        assert ab is not None
        assert ab.name == "inspect"
        assert conf >= 0.8

    def test_recount_matches_stats(self):
        ab, conf = find_ability("how many memories do I have")
        assert ab is not None
        assert ab.name == "recount"
        assert conf >= 0.8

    def test_no_match_for_open_ended(self):
        ab, conf = find_ability("what is the nature of consciousness?")
        assert ab is None
        assert conf == 0.0

    def test_no_match_for_gibberish(self):
        ab, conf = find_ability("xyzzy plugh")
        assert ab is None
        assert conf == 0.0

    def test_threshold_respected(self):
        # "tasks" is a keyword but only 0.6 confidence
        ab, conf = find_ability("tasks", threshold=0.8)
        assert ab is None

        ab, conf = find_ability("tasks", threshold=0.5)
        assert ab is not None


# ============================================================
# SCOUT (todo)
# ============================================================

class TestScout:

    def test_can_handle(self):
        ab = _REGISTRY["scout"]
        can, conf = ab.can_handle("generate todo")
        assert can is True
        assert conf == 0.9

    def test_can_handle_keyword(self):
        ab = _REGISTRY["scout"]
        can, conf = ab.can_handle("show me the tasks")
        assert can is True
        assert conf == 0.6

    def test_cannot_handle(self):
        ab = _REGISTRY["scout"]
        can, conf = ab.can_handle("explain quantum entanglement")
        assert can is False

    def test_execute(self, tmp_path):
        ab = _REGISTRY["scout"]
        (tmp_path / "CLAUDE.md").write_text("# Test")
        result = ab.execute("generate todo", {"project_root": str(tmp_path)})
        assert result["success"] is True
        assert "TODO.md" in result["result"]


# ============================================================
# RECALL
# ============================================================

class TestRecall:

    def test_can_handle(self):
        ab = _REGISTRY["recall"]
        can, conf = ab.can_handle("what did i decide about the API?")
        assert can is True
        assert conf >= 0.8

    def test_cannot_handle(self):
        ab = _REGISTRY["recall"]
        can, conf = ab.can_handle("write a function that sorts")
        assert can is False

    def test_execute_empty(self):
        ab = _REGISTRY["recall"]
        with patch("keanu.log.recall", return_value=[]):
            result = ab.execute("what did i decide?")
            assert result["success"] is True
            assert "No relevant memories" in result["result"]

    def test_execute_with_results(self):
        ab = _REGISTRY["recall"]
        with patch("keanu.log.recall", return_value=[
            {"memory_type": "decision", "content": "use postgres", "context": ""},
        ]):
            result = ab.execute("what did i decide?")
            assert result["success"] is True
            assert "1 relevant memories" in result["result"]
            assert "use postgres" in result["result"]


# ============================================================
# SCRY (detect)
# ============================================================

class TestScry:

    def test_can_handle_pattern_name(self):
        ab = _REGISTRY["scry"]
        can, conf = ab.can_handle("detect empathy_frustrated")
        assert can is True
        assert conf >= 0.8

    def test_can_handle_generic(self):
        ab = _REGISTRY["scry"]
        can, conf = ab.can_handle("check for patterns in this text")
        assert can is True
        assert conf >= 0.6

    def test_cannot_handle(self):
        ab = _REGISTRY["scry"]
        can, conf = ab.can_handle("what time is it?")
        assert can is False


# ============================================================
# ATTUNE (scan)
# ============================================================

class TestAttune:

    def test_can_handle_helix(self):
        ab = _REGISTRY["attune"]
        can, conf = ab.can_handle("helix scan this")
        assert can is True
        assert conf >= 0.8

    def test_cannot_handle_without_context(self):
        ab = _REGISTRY["attune"]
        can, conf = ab.can_handle("do something random")
        assert can is False

    def test_execute_no_file(self):
        ab = _REGISTRY["attune"]
        result = ab.execute("scan this", {})
        assert result["success"] is False
        assert "No file path" in result["result"]


# ============================================================
# PURGE (alive check)
# ============================================================

class TestPurge:

    def test_can_handle_alive_check(self):
        ab = _REGISTRY["purge"]
        can, conf = ab.can_handle("is this alive")
        assert can is True
        assert conf >= 0.9

    def test_can_handle_grey_or_black(self):
        ab = _REGISTRY["purge"]
        can, conf = ab.can_handle("alive or grey")
        assert can is True

    def test_can_handle_with_context(self):
        ab = _REGISTRY["purge"]
        can, conf = ab.can_handle("check alive", {"text": "some long response text here"})
        assert can is True

    def test_cannot_handle_generic(self):
        ab = _REGISTRY["purge"]
        can, conf = ab.can_handle("write me a poem")
        assert can is False

    def test_execute(self):
        ab = _REGISTRY["purge"]
        result = ab.execute("This is a thoughtful, specific response with real substance.")
        assert result["success"] is True
        assert "ALIVE" in result["result"]
        assert "state" in result["data"]


# ============================================================
# DECIPHER (signal)
# ============================================================

# ============================================================
# SOULSTONE (compress)
# ============================================================

class TestSoulstone:

    def test_can_handle(self):
        ab = _REGISTRY["soulstone"]
        can, conf = ab.can_handle("compress this")
        assert can is True
        assert conf >= 0.9

    def test_can_handle_coef(self):
        ab = _REGISTRY["soulstone"]
        can, conf = ab.can_handle("coef this module")
        assert can is True

    def test_cannot_handle(self):
        ab = _REGISTRY["soulstone"]
        can, conf = ab.can_handle("tell me a story")
        assert can is False

    def test_execute(self):
        ab = _REGISTRY["soulstone"]
        result = ab.execute("the quick brown fox jumps over the lazy dog")
        assert result["success"] is True
        assert "hash" in result["data"]
        assert result["data"]["size"] > 0


# ============================================================
# INSPECT (health)
# ============================================================

class TestInspect:

    def test_can_handle(self):
        ab = _REGISTRY["inspect"]
        can, conf = ab.can_handle("health check")
        assert can is True
        assert conf >= 0.9

    def test_can_handle_system_status(self):
        ab = _REGISTRY["inspect"]
        can, conf = ab.can_handle("system status")
        assert can is True

    def test_cannot_handle(self):
        ab = _REGISTRY["inspect"]
        can, conf = ab.can_handle("write code")
        assert can is False

    def test_execute(self):
        ab = _REGISTRY["inspect"]
        result = ab.execute("health check")
        assert result["success"] is True
        assert "modules" in result["data"]
        assert "abilities" in result["data"]
        assert result["data"]["abilities"] >= 15


# ============================================================
# RECOUNT (stats)
# ============================================================

class TestRecount:

    def test_can_handle(self):
        ab = _REGISTRY["recount"]
        can, conf = ab.can_handle("memory stats")
        assert can is True
        assert conf >= 0.9

    def test_can_handle_how_many(self):
        ab = _REGISTRY["recount"]
        can, conf = ab.can_handle("how many memories do I have")
        assert can is True
        assert conf >= 0.7

    def test_cannot_handle(self):
        ab = _REGISTRY["recount"]
        can, conf = ab.can_handle("bake the lenses")
        assert can is False

    def test_execute(self):
        ab = _REGISTRY["recount"]
        result = ab.execute("stats")
        assert result["success"] is True
        assert "total_memories" in result["data"]


# ============================================================
# ROUTER
# ============================================================

class TestRouter:

    def test_routes_to_ability(self):
        router = AbilityRouter()
        with patch.object(router, '_call_oracle') as mock_claude:
            result = router.route("generate todo", context={"project_root": "/tmp"})
            assert result.source == "ability"
            assert result.ability_name == "scout"
            mock_claude.assert_not_called()

    def test_routes_to_claude_when_no_ability(self):
        router = AbilityRouter()
        with patch.object(router, '_call_oracle', return_value=RouteResult(
            source="claude", response="deep answer"
        )) as mock_claude:
            result = router.route("what is the nature of truth?")
            assert result.source == "claude"
            mock_claude.assert_called_once()

    def test_stats_tracking(self):
        router = AbilityRouter()
        router.route("generate todo", context={"project_root": "/tmp"})
        stats = router.stats()
        assert stats["ability_hits"] == 1
        assert stats["claude_hits"] == 0

    def test_route_result_fields(self):
        r = RouteResult(source="ability", response="done",
                        ability_name="scout", confidence=0.9)
        assert r.source == "ability"
        assert r.response == "done"
        assert r.ability_name == "scout"
        assert r.confidence == 0.9


# ============================================================
# HANDS (invoked by loop, not by natural language)
# ============================================================

class TestHands:

    def test_hands_never_match_natural_language(self):
        """Hands abilities return False from can_handle. Loop invokes directly."""
        for name in ["read", "write", "edit", "search", "ls", "run"]:
            ab = _REGISTRY[name]
            can, conf = ab.can_handle("read the file please")
            assert can is False, f"{name} should not match natural language"

    def test_read_execute(self, tmp_path):
        ab = _REGISTRY["read"]
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        with patch("keanu.abilities.hands.hands._is_safe_path", return_value=True):
            result = ab.execute("", {"file_path": str(f)})
        assert result["success"] is True
        assert "hello world" in result["result"]

    def test_read_no_path(self):
        ab = _REGISTRY["read"]
        result = ab.execute("", {})
        assert result["success"] is False

    def test_write_execute(self, tmp_path):
        ab = _REGISTRY["write"]
        f = tmp_path / "out.txt"
        with patch("keanu.abilities.hands.hands._is_safe_path", return_value=True):
            result = ab.execute("", {"file_path": str(f), "content": "wrote this"})
        assert result["success"] is True
        assert f.read_text() == "wrote this"

    def test_edit_execute(self, tmp_path):
        ab = _REGISTRY["edit"]
        f = tmp_path / "edit_me.txt"
        f.write_text("old value here")
        with patch("keanu.abilities.hands.hands._is_safe_path", return_value=True):
            result = ab.execute("", {
                "file_path": str(f),
                "old_string": "old value",
                "new_string": "new value",
            })
        assert result["success"] is True
        assert "new value here" in f.read_text()

    def test_edit_rejects_non_unique(self, tmp_path):
        ab = _REGISTRY["edit"]
        f = tmp_path / "dupe.txt"
        f.write_text("aaa\naaa\n")
        with patch("keanu.abilities.hands.hands._is_safe_path", return_value=True):
            result = ab.execute("", {
                "file_path": str(f),
                "old_string": "aaa",
                "new_string": "bbb",
            })
        assert result["success"] is False
        assert "2 times" in result["result"]

    def test_run_blocked_command(self):
        ab = _REGISTRY["run"]
        result = ab.execute("", {"command": "sudo rm -rf /"})
        assert result["success"] is False
        assert "blocked" in result["result"].lower()

    def test_run_safe_command(self):
        ab = _REGISTRY["run"]
        result = ab.execute("", {"command": "echo hello"})
        assert result["success"] is True
        assert "hello" in result["result"]


# ============================================================
# CAST LINES
# ============================================================

class TestCastLines:

    def test_every_ability_has_cast_line(self):
        """every ability in the registry must have a non-empty cast_line."""
        for ab in _REGISTRY.values():
            assert ab.cast_line, f"{ab.name} missing cast_line"

    def test_cast_lines_end_with_ellipsis(self):
        """cast lines should end with ... for consistency."""
        for ab in _REGISTRY.values():
            assert ab.cast_line.endswith("..."), (
                f"{ab.name} cast_line should end with '...': {ab.cast_line}"
            )

    def test_list_abilities_includes_cast_line(self):
        abilities = list_abilities()
        for ab in abilities:
            assert "cast_line" in ab, f"{ab['name']} missing cast_line in list_abilities"
            assert ab["cast_line"], f"{ab['name']} has empty cast_line"


# ============================================================
# GRIMOIRE
# ============================================================

class TestGrimoire:

    def test_record_cast_first_use(self, tmp_path, monkeypatch):
        grimoire_path = tmp_path / "grimoire.json"
        monkeypatch.setattr("keanu.abilities.GRIMOIRE", grimoire_path)
        assert record_cast("scry") is True

    def test_record_cast_subsequent_use(self, tmp_path, monkeypatch):
        grimoire_path = tmp_path / "grimoire.json"
        monkeypatch.setattr("keanu.abilities.GRIMOIRE", grimoire_path)
        record_cast("scry")
        assert record_cast("scry") is False

    def test_use_count_increments(self, tmp_path, monkeypatch):
        grimoire_path = tmp_path / "grimoire.json"
        monkeypatch.setattr("keanu.abilities.GRIMOIRE", grimoire_path)
        record_cast("read")
        record_cast("read")
        record_cast("read")
        g = get_grimoire()
        assert g["read"]["use_count"] == 3

    def test_get_grimoire_empty(self, tmp_path, monkeypatch):
        grimoire_path = tmp_path / "grimoire.json"
        monkeypatch.setattr("keanu.abilities.GRIMOIRE", grimoire_path)
        assert get_grimoire() == {}

    def test_multiple_abilities_tracked(self, tmp_path, monkeypatch):
        grimoire_path = tmp_path / "grimoire.json"
        monkeypatch.setattr("keanu.abilities.GRIMOIRE", grimoire_path)
        record_cast("scry")
        record_cast("recall")
        record_cast("fuse")
        g = get_grimoire()
        assert len(g) == 3
        assert "scry" in g
        assert "recall" in g
        assert "fuse" in g
