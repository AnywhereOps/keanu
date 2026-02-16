"""tests for lint and format abilities."""

from unittest.mock import patch, MagicMock
import subprocess

from keanu.abilities.hands.lint import (
    LintAbility, FormatAbility,
    _detect_lint_command, _detect_format_command,
    _parse_lint_issues, _run_tool,
)


class TestRunTool:

    def test_success(self):
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(
                stdout="all good", stderr="", returncode=0,
            )
            result = _run_tool("ruff check .")
            assert result["success"]
            assert "all good" in result["result"]

    def test_failure(self):
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(
                stdout="error on line 5", stderr="", returncode=1,
            )
            result = _run_tool("ruff check .")
            assert not result["success"]
            assert "error" in result["result"]

    def test_clean_output(self):
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(
                stdout="", stderr="", returncode=0,
            )
            result = _run_tool("ruff check .")
            assert result["success"]
            assert "(clean)" in result["result"]

    def test_timeout(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("x", 60)):
            result = _run_tool("slow_lint .")
            assert not result["success"]
            assert "Timed out" in result["result"]

    def test_not_found(self):
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = _run_tool("nonexistent_tool .")
            assert not result["success"]
            assert "not found" in result["result"]


class TestParseLintIssues:

    def test_ruff_format(self):
        output = (
            "src/foo.py:10:5: E501 line too long\n"
            "src/bar.py:20:1: F401 unused import\n"
        )
        issues = _parse_lint_issues(output)
        assert len(issues) == 2
        assert issues[0]["file"] == "src/foo.py"
        assert issues[0]["line"] == 10
        assert "E501" in issues[0]["message"]
        assert issues[1]["file"] == "src/bar.py"
        assert issues[1]["line"] == 20

    def test_empty_output(self):
        assert _parse_lint_issues("") == []

    def test_caps_at_50(self):
        lines = "\n".join(f"f.py:{i}:1: E501 long" for i in range(100))
        issues = _parse_lint_issues(lines)
        assert len(issues) == 50


class TestDetectLintCommand:

    def test_uses_project_model(self):
        mock_model = MagicMock()
        mock_model.lint_command = "ruff check ."
        with patch("keanu.project.detect", return_value=mock_model):
            cmd = _detect_lint_command(".")
            assert cmd == "ruff check ."

    def test_fallback_python(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\n")
        # patch detect to fail so fallback kicks in
        with patch("keanu.project.detect", side_effect=Exception("no")):
            cmd = _detect_lint_command(str(tmp_path))
            assert "ruff" in cmd

    def test_fallback_node(self, tmp_path):
        (tmp_path / "package.json").write_text("{}")
        with patch("keanu.project.detect", side_effect=Exception("no")):
            cmd = _detect_lint_command(str(tmp_path))
            assert "eslint" in cmd


class TestDetectFormatCommand:

    def test_uses_project_model(self):
        mock_model = MagicMock()
        mock_model.format_command = "black ."
        with patch("keanu.project.detect", return_value=mock_model):
            cmd = _detect_format_command(".")
            assert cmd == "black ."

    def test_fallback_go(self, tmp_path):
        (tmp_path / "go.mod").write_text("module foo\n")
        with patch("keanu.project.detect", side_effect=Exception("no")):
            cmd = _detect_format_command(str(tmp_path))
            assert "gofmt" in cmd


class TestLintAbility:

    def test_execute_success(self):
        ab = LintAbility()
        with patch("keanu.abilities.hands.lint._run_tool") as mock:
            mock.return_value = {"success": True, "result": "(clean)", "data": {}}
            result = ab.execute("", context={"path": "."})
            assert result["success"]

    def test_fix_mode_ruff(self):
        ab = LintAbility()
        with patch("keanu.abilities.hands.lint._run_tool") as mock:
            mock.return_value = {"success": True, "result": "fixed", "data": {}}
            with patch("keanu.abilities.hands.lint._detect_lint_command", return_value="ruff check ."):
                ab.execute("", context={"fix": True})
                call_cmd = mock.call_args[0][0]
                assert "--fix" in call_cmd

    def test_parses_issues_on_failure(self):
        ab = LintAbility()
        with patch("keanu.abilities.hands.lint._run_tool") as mock:
            mock.return_value = {
                "success": False,
                "result": "foo.py:1:1: E501 long line",
                "data": {},
            }
            result = ab.execute("", context={})
            assert result["data"]["issue_count"] == 1


class TestFormatAbility:

    def test_execute_success(self):
        ab = FormatAbility()
        with patch("keanu.abilities.hands.lint._run_tool") as mock:
            mock.return_value = {"success": True, "result": "formatted", "data": {}}
            result = ab.execute("", context={"path": "."})
            assert result["success"]

    def test_check_only_ruff(self):
        ab = FormatAbility()
        with patch("keanu.abilities.hands.lint._run_tool") as mock:
            mock.return_value = {"success": True, "result": "ok", "data": {}}
            with patch("keanu.abilities.hands.lint._detect_format_command", return_value="ruff format ."):
                ab.execute("", context={"check": True})
                call_cmd = mock.call_args[0][0]
                assert "--check" in call_cmd
