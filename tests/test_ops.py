"""tests for proactive ops monitoring."""

import json
import time
from pathlib import Path
from unittest.mock import patch

from keanu.abilities.world.ops import (
    check_stale_deps, check_test_health, check_doc_drift,
    check_code_quality, check_git_hygiene,
    scan, get_ops_history, should_scan,
    OpsIssue, OpsReport,
)


class TestOpsIssue:

    def test_to_dict(self):
        issue = OpsIssue("deps", "warning", "outdated", file="req.txt")
        d = issue.to_dict()
        assert d["category"] == "deps"
        assert d["severity"] == "warning"
        assert d["file"] == "req.txt"


class TestOpsReport:

    def test_empty(self):
        report = OpsReport()
        assert report.critical_count == 0
        assert report.warning_count == 0
        assert "all clear" in report.summary()

    def test_with_issues(self):
        report = OpsReport(issues=[
            OpsIssue("deps", "critical", "vuln"),
            OpsIssue("tests", "warning", "low coverage"),
            OpsIssue("docs", "info", "stale"),
        ])
        assert report.critical_count == 1
        assert report.warning_count == 1
        assert "3 issues" in report.summary()

    def test_fixable_count(self):
        report = OpsReport(issues=[
            OpsIssue("deps", "info", "update", auto_fixable=True),
            OpsIssue("code", "info", "big file", auto_fixable=False),
        ])
        assert report.fixable_count == 1

    def test_to_dict(self):
        report = OpsReport(issues=[OpsIssue("a", "info", "b")], checks_run=3)
        d = report.to_dict()
        assert d["checks_run"] == 3
        assert len(d["issues"]) == 1


class TestCheckTestHealth:

    def test_no_tests(self, tmp_path):
        issues = check_test_health(str(tmp_path))
        assert any("no test directory" in i.message for i in issues)

    def test_has_tests(self, tmp_path):
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_foo.py").write_text("def test_x(): pass\n")
        issues = check_test_health(str(tmp_path))
        assert not any("no test directory" in i.message for i in issues)

    def test_low_ratio(self, tmp_path):
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_one.py").write_text("def test(): pass\n")
        src = tmp_path / "src"
        src.mkdir()
        for i in range(10):
            (src / f"mod{i}.py").write_text(f"x = {i}\n")
        issues = check_test_health(str(tmp_path))
        assert any("low test coverage" in i.message for i in issues)


class TestCheckDocDrift:

    def test_no_readme(self, tmp_path):
        issues = check_doc_drift(str(tmp_path))
        assert any("no README" in i.message for i in issues)

    def test_has_readme(self, tmp_path):
        (tmp_path / "README.md").write_text("# Project\n")
        issues = check_doc_drift(str(tmp_path))
        assert not any("no README" in i.message for i in issues)

    def test_stale_todos(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        lines = "\n".join(f"# TODO: fix thing {i}" for i in range(25))
        (src / "big.py").write_text(lines)
        issues = check_doc_drift(str(tmp_path))
        assert any("TODO" in i.message for i in issues)


class TestCheckCodeQuality:

    def test_no_src(self, tmp_path):
        issues = check_code_quality(str(tmp_path))
        assert len(issues) == 0

    def test_large_file(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "big.py").write_text("x = 1\n" * 600)
        issues = check_code_quality(str(tmp_path))
        assert any("lines" in i.message and "big.py" in i.message for i in issues)

    def test_small_files_ok(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "small.py").write_text("x = 1\n" * 50)
        issues = check_code_quality(str(tmp_path))
        assert len(issues) == 0


class TestCheckGitHygiene:

    def test_no_git(self, tmp_path):
        issues = check_git_hygiene(str(tmp_path))
        assert len(issues) == 0

    def test_no_gitignore(self, tmp_path):
        (tmp_path / ".git").mkdir()
        issues = check_git_hygiene(str(tmp_path))
        assert any(".gitignore" in i.message for i in issues)


class TestScan:

    def test_scan_all(self, tmp_path):
        log_file = tmp_path / "ops.jsonl"
        with patch("keanu.abilities.world.ops._OPS_LOG", log_file):
            report = scan(str(tmp_path))
            assert report.checks_run >= 4
            assert isinstance(report.issues, list)

    def test_scan_specific(self, tmp_path):
        log_file = tmp_path / "ops.jsonl"
        with patch("keanu.abilities.world.ops._OPS_LOG", log_file):
            report = scan(str(tmp_path), checks=["docs", "code"])
            assert report.checks_run == 2

    def test_scan_logs(self, tmp_path):
        log_file = tmp_path / "ops.jsonl"
        with patch("keanu.abilities.world.ops._OPS_LOG", log_file):
            scan(str(tmp_path))
            assert log_file.exists()


class TestOpsHistory:

    def test_empty(self, tmp_path):
        with patch("keanu.abilities.world.ops._OPS_LOG", tmp_path / "nope.jsonl"):
            assert get_ops_history() == []

    def test_reads_log(self, tmp_path):
        log_file = tmp_path / "ops.jsonl"
        log_file.write_text(json.dumps({"timestamp": 1, "issue_count": 3}) + "\n")
        with patch("keanu.abilities.world.ops._OPS_LOG", log_file):
            history = get_ops_history()
            assert len(history) == 1
            assert history[0]["issue_count"] == 3


class TestShouldScan:

    def test_never_scanned(self, tmp_path):
        with patch("keanu.abilities.world.ops._OPS_LOG", tmp_path / "nope.jsonl"):
            assert should_scan()

    def test_recently_scanned(self, tmp_path):
        log_file = tmp_path / "ops.jsonl"
        log_file.write_text(json.dumps({"timestamp": time.time()}) + "\n")
        with patch("keanu.abilities.world.ops._OPS_LOG", log_file):
            assert not should_scan(interval_hours=24)

    def test_old_scan(self, tmp_path):
        log_file = tmp_path / "ops.jsonl"
        log_file.write_text(json.dumps({"timestamp": time.time() - 100000}) + "\n")
        with patch("keanu.abilities.world.ops._OPS_LOG", log_file):
            assert should_scan(interval_hours=24)
