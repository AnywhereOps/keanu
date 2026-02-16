"""tests for bisect.py - git bisect helpers."""

from keanu.data.bisect import (
    BisectResult,
    BisectStep,
    analyze_bisect_log,
    binary_search_commits,
    build_bisect_script,
    estimate_steps,
    find_commits_between,
    format_bisect_report,
    parse_git_log,
    suggest_test_command,
    _run_test_at_commit,
)
from unittest.mock import patch, MagicMock


class TestParseGitLog:
    def test_oneline_format(self):
        log = "abc1234 fix the thing\ndef5678 add feature\n"
        result = parse_git_log(log)
        assert len(result) == 2
        assert result[0]["hash"] == "abc1234"
        assert result[0]["message"] == "fix the thing"

    def test_pipe_delimited_format(self):
        log = "abc1234|Drew|2024-01-15|fix the thing\n"
        result = parse_git_log(log)
        assert len(result) == 1
        assert result[0]["author"] == "Drew"
        assert result[0]["date"] == "2024-01-15"
        assert result[0]["message"] == "fix the thing"

    def test_empty_input(self):
        assert parse_git_log("") == []
        assert parse_git_log("   \n  \n") == []

    def test_hash_only(self):
        result = parse_git_log("abc1234\n")
        assert len(result) == 1
        assert result[0]["hash"] == "abc1234"
        assert result[0]["message"] == ""

    def test_pipe_three_fields(self):
        result = parse_git_log("abc|drew|the message\n")
        assert result[0]["author"] == "drew"
        assert result[0]["message"] == "the message"


class TestFindCommitsBetween:
    @patch("keanu.data.bisect.subprocess.run")
    def test_returns_hashes(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="aaa\nbbb\nccc\n"
        )
        result = find_commits_between("good", "bad", "/tmp")
        assert result == ["aaa", "bbb", "ccc"]
        mock_run.assert_called_once()

    @patch("keanu.data.bisect.subprocess.run")
    def test_returns_empty_on_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        assert find_commits_between("good", "bad") == []


class TestRunTestAtCommit:
    def test_builds_command_string(self):
        passed, output = _run_test_at_commit("abc123", "pytest -x", "/repo")
        assert "git checkout abc123" in output
        assert "pytest -x" in output
        assert "/repo" in output


class TestBuildBisectScript:
    def test_generates_valid_script(self):
        script = build_bisect_script("pytest -x", "aaa", "bbb")
        assert script.startswith("#!/bin/bash")
        assert "git bisect start bbb aaa" in script
        assert "git bisect run pytest -x" in script
        assert "git bisect reset" in script

    def test_contains_set_e(self):
        script = build_bisect_script("make test", "g", "b")
        assert "set -e" in script


class TestAnalyzeBisectLog:
    def test_parses_full_log(self):
        log = """# bad: [deadbeef] broke everything
# good: [cafebabe] last known good
git bisect start 'deadbeef' 'cafebabe'
# good: [111aaa] intermediate commit
git bisect good 111aaa
# bad: [222bbb] another commit
git bisect bad 222bbb
# first bad commit: [222bbb] another commit that broke it
"""
        result = analyze_bisect_log(log)
        assert result.bad_commit == "deadbeef"
        assert result.good_commit == "cafebabe"
        assert result.culprit_commit == "222bbb"
        assert result.culprit_message == "another commit that broke it"
        assert result.steps > 0
        assert "111aaa" in result.commits_tested

    def test_empty_log(self):
        result = analyze_bisect_log("")
        assert result.culprit_commit == ""
        assert result.steps == 0


class TestFormatBisectReport:
    def test_contains_all_fields(self):
        r = BisectResult(
            bad_commit="bad1",
            good_commit="good1",
            culprit_commit="culp1",
            culprit_message="broke it",
            steps=3,
            commits_tested=["a", "b", "c"],
        )
        report = format_bisect_report(r)
        assert "bad1" in report
        assert "good1" in report
        assert "culp1" in report
        assert "broke it" in report
        assert "3" in report

    def test_empty_commits_tested(self):
        r = BisectResult("b", "g", "c", "msg", 0)
        report = format_bisect_report(r)
        assert "\n  " not in report


class TestSuggestTestCommand:
    def test_import_error(self):
        cmd = suggest_test_command("import error in keanu")
        assert "import keanu" in cmd

    def test_test_fails(self):
        cmd = suggest_test_command("test_alive fails")
        assert "pytest" in cmd
        assert "alive" in cmd

    def test_syntax_error_with_file(self):
        cmd = suggest_test_command("syntax error in foo.py")
        assert "py_compile" in cmd
        assert "foo.py" in cmd

    def test_build_failure(self):
        cmd = suggest_test_command("build is broken")
        assert "build" in cmd

    def test_type_error(self):
        cmd = suggest_test_command("type check error")
        assert "mypy" in cmd

    def test_generic_fallback(self):
        cmd = suggest_test_command("something is wrong")
        assert cmd == "pytest -x"


class TestBinarySearchCommits:
    def test_finds_first_bad(self):
        commits = ["a", "b", "c", "d", "e", "f", "g", "h"]
        # good: a-d, bad: e-h (first bad at index 4)
        idx, steps = binary_search_commits(
            commits, lambda c: commits.index(c) < 4
        )
        assert idx == 4
        assert len(steps) > 0
        assert all(isinstance(s, BisectStep) for s in steps)

    def test_first_commit_bad(self):
        commits = ["a", "b", "c"]
        idx, steps = binary_search_commits(commits, lambda c: False)
        assert idx == 0

    def test_empty_list(self):
        idx, steps = binary_search_commits([], lambda c: True)
        assert idx == -1
        assert steps == []

    def test_two_commits(self):
        commits = ["good", "bad"]
        idx, steps = binary_search_commits(
            commits, lambda c: c == "good"
        )
        assert idx == 1

    def test_step_results_recorded(self):
        commits = list("abcdefgh")
        _, steps = binary_search_commits(
            commits, lambda c: commits.index(c) < 5
        )
        for s in steps:
            assert s.result in ("good", "bad")
            assert s.commit in commits


class TestEstimateSteps:
    def test_power_of_two(self):
        assert estimate_steps(8) == 3
        assert estimate_steps(16) == 4

    def test_non_power(self):
        assert estimate_steps(10) == 4
        assert estimate_steps(100) == 7

    def test_edge_cases(self):
        assert estimate_steps(0) == 0
        assert estimate_steps(1) == 0
        assert estimate_steps(2) == 1
