"""Tests for proc.py - subprocess execution and process management."""

import os
import sys

from keanu.tools.proc import (
    RunResult,
    parse_command,
    run,
    run_pipeline,
    safe_env,
    which,
    is_running,
)


class TestRunResult:
    def test_ok_when_zero(self):
        r = RunResult(command="true", returncode=0)
        assert r.ok is True

    def test_not_ok_when_nonzero(self):
        r = RunResult(command="false", returncode=1)
        assert r.ok is False

    def test_not_ok_when_timed_out(self):
        r = RunResult(command="sleep 10", returncode=-1, timed_out=True)
        assert r.ok is False

    def test_fields(self):
        r = RunResult(
            command=["echo", "hi"],
            returncode=0,
            stdout="hi\n",
            stderr="",
            elapsed_ms=5.0,
            timed_out=False,
        )
        assert r.command == ["echo", "hi"]
        assert r.stdout == "hi\n"
        assert r.elapsed_ms == 5.0


class TestRun:
    def test_echo(self):
        r = run("echo hello")
        assert r.ok
        assert r.stdout.strip() == "hello"
        assert r.returncode == 0

    def test_true(self):
        r = run("true")
        assert r.ok

    def test_false(self):
        r = run("false")
        assert not r.ok
        assert r.returncode != 0

    def test_captures_stderr(self):
        r = run([sys.executable, "-c", "import sys; sys.stderr.write('oops')"])
        assert "oops" in r.stderr

    def test_captures_stdout(self):
        r = run([sys.executable, "-c", "print('yes')"])
        assert r.stdout.strip() == "yes"

    def test_timeout(self):
        r = run("sleep 10", timeout=1)
        assert r.timed_out is True
        assert not r.ok
        assert r.returncode == -1

    def test_elapsed_ms(self):
        r = run("true")
        assert r.elapsed_ms >= 0

    def test_with_cwd(self):
        r = run("pwd", cwd="/tmp")
        assert r.ok
        # macOS /tmp -> /private/tmp
        assert "tmp" in r.stdout

    def test_command_not_found(self):
        r = run("definitely_not_a_real_command_xyz")
        assert not r.ok
        assert r.returncode == 127

    def test_list_command(self):
        r = run(["echo", "from list"])
        assert r.ok
        assert "from list" in r.stdout


class TestRunPipeline:
    def test_all_succeed(self):
        results = run_pipeline(["true", "echo done"])
        assert len(results) == 2
        assert all(r.ok for r in results)

    def test_stops_on_failure(self):
        results = run_pipeline(["true", "false", "echo never"])
        assert len(results) == 2
        assert results[0].ok
        assert not results[1].ok

    def test_empty(self):
        results = run_pipeline([])
        assert results == []


class TestParseCommand:
    def test_simple(self):
        assert parse_command("echo hello") == ["echo", "hello"]

    def test_quoted(self):
        assert parse_command('echo "hello world"') == ["echo", "hello world"]

    def test_single_quotes(self):
        assert parse_command("echo 'hello world'") == ["echo", "hello world"]

    def test_complex(self):
        parts = parse_command("git commit -m 'fix: the thing'")
        assert parts == ["git", "commit", "-m", "fix: the thing"]


class TestWhich:
    def test_finds_python(self):
        # python3 or python should exist
        result = which("python3") or which("python")
        assert result is not None

    def test_nonexistent(self):
        assert which("definitely_not_a_real_binary_xyz") is None


class TestSafeEnv:
    def test_strips_api_keys(self):
        env = safe_env({"MY_API_KEY": "secret123", "NORMAL": "ok"})
        assert "MY_API_KEY" not in env
        assert env["NORMAL"] == "ok"

    def test_strips_tokens(self):
        env = safe_env({"GITHUB_TOKEN": "ghp_abc", "PATH": "/usr/bin"})
        assert "GITHUB_TOKEN" not in env
        assert "PATH" in env

    def test_strips_secrets(self):
        env = safe_env({"DB_SECRET": "s3cret", "HOME": "/home/user"})
        assert "DB_SECRET" not in env
        assert "HOME" in env

    def test_strips_passwords(self):
        env = safe_env({"DB_PASSWORD": "pass", "SHELL": "/bin/zsh"})
        assert "DB_PASSWORD" not in env
        assert "SHELL" in env

    def test_no_extra(self):
        env = safe_env()
        assert "PATH" in env

    def test_case_insensitive_strip(self):
        env = safe_env({"my_Api_Key": "x"})
        assert "my_Api_Key" not in env


class TestIsRunning:
    def test_current_process(self):
        assert is_running(os.getpid()) is True

    def test_nonexistent_pid(self):
        # PID 99999999 almost certainly doesn't exist
        assert is_running(99999999) is False
