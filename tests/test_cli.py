"""Tests for cli.py - verify commands parse without crashing."""

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

    def test_do_help(self):
        r = _run_keanu("do", "--help")
        assert r.returncode == 0
        assert "--craft" in r.stdout
        assert "--prove" in r.stdout

    def test_ask_help(self):
        r = _run_keanu("ask", "--help")
        assert r.returncode == 0

    def test_memory_help(self):
        r = _run_keanu("memory", "--help")
        assert r.returncode == 0
        assert "remember" in r.stdout
        assert "recall" in r.stdout

    def test_memory_remember_help(self):
        r = _run_keanu("memory", "remember", "--help")
        assert r.returncode == 0

    def test_memory_recall_help(self):
        r = _run_keanu("memory", "recall", "--help")
        assert r.returncode == 0

    def test_memory_plan_help(self):
        r = _run_keanu("memory", "plan", "--help")
        assert r.returncode == 0

    def test_remember_shortcut(self):
        r = _run_keanu("remember", "--help")
        assert r.returncode == 0

    def test_recall_shortcut(self):
        r = _run_keanu("recall", "--help")
        assert r.returncode == 0

    def test_detect_help(self):
        r = _run_keanu("detect", "--help")
        assert r.returncode == 0

    def test_memory_stats(self):
        r = _run_keanu("memory", "stats")
        assert r.returncode == 0
        assert "memberberry" in r.stdout

    def test_healthz(self):
        r = _run_keanu("healthz")
        assert r.returncode == 0
        assert "keanu health" in r.stdout
        assert "ORACLE" in r.stdout
        assert "VECTORS" in r.stdout
        assert "MEMORY" in r.stdout
        assert "FORGE" in r.stdout
        assert "MODULES" in r.stdout
        assert "EXTERNAL DEPS" in r.stdout

    def test_healthz_alias(self):
        r = _run_keanu("health")
        assert r.returncode == 0
        assert "keanu health" in r.stdout

    def test_no_args_launches_repl(self):
        r = _run_keanu()
        assert r.returncode == 0
        assert "type a task" in r.stdout
