"""Tests for cli.py - verify all commands parse without crashing."""

import subprocess
import sys


def _run_keanu(*args):
    result = subprocess.run(
        [sys.executable, "-m", "keanu.cli", *args],
        capture_output=True, text=True, timeout=10,
    )
    return result


class TestCLIHelp:
    def test_help(self):
        r = _run_keanu("--help")
        assert r.returncode == 0
        assert "keanu" in r.stdout

    def test_scan_help(self):
        r = _run_keanu("scan", "--help")
        assert r.returncode == 0

    def test_remember_help(self):
        r = _run_keanu("remember", "--help")
        assert r.returncode == 0

    def test_recall_help(self):
        r = _run_keanu("recall", "--help")
        assert r.returncode == 0

    def test_plan_help(self):
        r = _run_keanu("plan", "--help")
        assert r.returncode == 0

    def test_detect_help(self):
        r = _run_keanu("detect", "--help")
        assert r.returncode == 0

    def test_stats(self):
        r = _run_keanu("stats")
        assert r.returncode == 0
        assert "memberberry" in r.stdout

    def test_healthz(self):
        r = _run_keanu("healthz")
        assert r.returncode == 0
        assert "keanu health" in r.stdout
        assert "MEMORY" in r.stdout
        assert "MODULES" in r.stdout
        assert "SIGNAL" in r.stdout

    def test_healthz_alias(self):
        r = _run_keanu("health")
        assert r.returncode == 0
        assert "keanu health" in r.stdout

    def test_no_args_shows_help(self):
        r = _run_keanu()
        # exits 1 with help text
        assert r.returncode == 1
