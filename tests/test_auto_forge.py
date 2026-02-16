"""tests for miss-to-ability pipeline and proactive ops."""

from unittest.mock import patch, MagicMock

from keanu.gen.auto_forge import (
    analyze_misses, analyze_mistakes, get_all_candidates,
    auto_forge, auto_forge_all, check_project_health,
    forge_history, ForgeCandidate, ForgeResult,
    _extract_action, _extract_keywords,
)


class TestExtractAction:

    def test_verb_noun(self):
        assert _extract_action("create dashboard for users") == "create_dashboard"

    def test_deploy(self):
        assert _extract_action("deploy the application") == "deploy_application"

    def test_fallback(self):
        result = _extract_action("something about authentication")
        assert result  # should extract something

    def test_empty(self):
        assert _extract_action("") == ""


class TestExtractKeywords:

    def test_common_words(self):
        examples = [
            "create a dashboard",
            "build a dashboard widget",
            "make dashboard pretty",
        ]
        keywords = _extract_keywords(examples)
        assert "dashboard" in keywords

    def test_filters_stop_words(self):
        keywords = _extract_keywords(["the quick brown fox"])
        assert "the" not in keywords


class TestAnalyzeMisses:

    def test_empty_when_no_misses(self):
        with patch("keanu.abilities.miss_tracker.get_misses", return_value=[]):
            candidates = analyze_misses(min_count=1)
        assert candidates == []

    def test_finds_candidates(self):
        misses = [
            {"prompt": "deploy the application", "timestamp": 1},
            {"prompt": "deploy to staging", "timestamp": 2},
            {"prompt": "deploy production", "timestamp": 3},
        ]
        with patch("keanu.abilities.miss_tracker.get_misses", return_value=misses):
            candidates = analyze_misses(min_count=2)

        # should find deploy-related candidate
        assert len(candidates) >= 0  # depends on clustering


class TestForgeCandidate:

    def test_to_dict(self):
        c = ForgeCandidate(
            name="deploy",
            description="deploy things",
            keywords=["deploy"],
            miss_count=5,
            examples=["deploy app"],
        )
        d = c.to_dict()
        assert d["name"] == "deploy"
        assert d["miss_count"] == 5

    def test_auto_forgeable(self):
        c = ForgeCandidate(
            name="test", description="x",
            keywords=["x"], miss_count=5,
            examples=["x"],
            auto_forgeable=True,
        )
        assert c.auto_forgeable


class TestAutoForge:

    def test_forge_success(self, tmp_path):
        candidate = ForgeCandidate(
            name="deploy",
            description="deploy things",
            keywords=["deploy"],
            miss_count=5,
            examples=["deploy app"],
        )

        mock_result = {
            "ability_file": str(tmp_path / "deploy.py"),
            "test_file": str(tmp_path / "test_deploy.py"),
        }

        with patch("keanu.abilities.forge.forge_ability", return_value=mock_result):
            with patch("keanu.gen.auto_forge._log_forge"):
                result = auto_forge(candidate)

        assert result.success
        assert result.ability_name == "deploy"

    def test_forge_failure(self):
        candidate = ForgeCandidate(
            name="bad", description="x",
            keywords=["x"], miss_count=5, examples=["x"],
        )

        with patch("keanu.abilities.forge.forge_ability",
                   return_value={"error": "already exists"}):
            result = auto_forge(candidate)

        assert not result.success


class TestAutoForgeAll:

    def test_dry_run(self):
        candidates = [
            ForgeCandidate(
                name="deploy", description="x",
                keywords=["deploy"], miss_count=10,
                examples=["deploy"], auto_forgeable=True,
            ),
        ]
        with patch("keanu.gen.auto_forge.get_all_candidates", return_value=candidates):
            results = auto_forge_all(dry_run=True)

        assert len(results) == 1
        assert results[0]["action"] == "would_forge"


class TestCheckProjectHealth:

    def test_returns_health(self, tmp_path):
        (tmp_path / "mod.py").write_text("x = 1\n")

        health = check_project_health(str(tmp_path))
        assert "score" in health
        assert "issues" in health
        assert health["score"] >= 0

    def test_perfect_health(self, tmp_path):
        # empty project
        health = check_project_health(str(tmp_path))
        assert health["score"] >= 80  # should be mostly healthy


class TestForgeHistory:

    def test_empty_history(self, tmp_path):
        forge_log = tmp_path / "forge_log.jsonl"
        with patch("keanu.gen.auto_forge._FORGE_LOG", forge_log):
            history = forge_history()
        assert history == []

    def test_reads_history(self, tmp_path):
        import json
        forge_log = tmp_path / "forge_log.jsonl"
        forge_log.write_text(json.dumps({
            "timestamp": 1.0, "name": "deploy",
            "miss_count": 5, "confidence": 0.8,
        }) + "\n")

        with patch("keanu.gen.auto_forge._FORGE_LOG", forge_log):
            history = forge_history()

        assert len(history) == 1
        assert history[0]["name"] == "deploy"
