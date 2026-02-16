"""proc.py - safe subprocess execution with timeout and process management.

run commands, capture output, handle timeouts. track background processes.
used by the run ability, test runner, lint, and git operations.

in the world: the hands need a body. this is how keanu touches the filesystem
and runs tools without losing control.
"""

import os
import shlex
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

# keys containing these substrings get stripped from safe_env
_SENSITIVE = {"api_key", "api_secret", "token", "secret", "password", "credential"}


@dataclass
class RunResult:
    """result of a subprocess run."""

    command: str | list
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""
    elapsed_ms: float = 0.0
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        """true if returncode is 0 and no timeout."""
        return self.returncode == 0 and not self.timed_out


@dataclass
class _TrackedProcess:
    """internal record for a background process."""

    proc: subprocess.Popen
    cmd: str | list
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# background process registry
_registry: dict[int, _TrackedProcess] = {}


def parse_command(cmd: str) -> list[str]:
    """split a command string into args list."""
    return shlex.split(cmd)


def run(
    cmd: str | list,
    timeout: int = 60,
    cwd: str | None = None,
    env: dict | None = None,
    capture: bool = True,
    shell: bool = False,
) -> RunResult:
    """run a command, capture output, handle timeout gracefully."""
    if isinstance(cmd, str) and not shell:
        args = shlex.split(cmd)
    else:
        args = cmd

    merged_env = safe_env(env) if env else None
    start = time.monotonic()

    try:
        proc = subprocess.run(
            args,
            capture_output=capture,
            text=True if capture else None,
            timeout=timeout,
            cwd=cwd,
            env=merged_env,
            shell=shell,
        )
        elapsed = (time.monotonic() - start) * 1000
        return RunResult(
            command=cmd,
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            elapsed_ms=round(elapsed, 2),
        )
    except subprocess.TimeoutExpired:
        elapsed = (time.monotonic() - start) * 1000
        return RunResult(
            command=cmd,
            returncode=-1,
            stderr=f"timed out after {timeout}s",
            elapsed_ms=round(elapsed, 2),
            timed_out=True,
        )
    except FileNotFoundError:
        elapsed = (time.monotonic() - start) * 1000
        return RunResult(
            command=cmd,
            returncode=127,
            stderr=f"command not found: {args[0] if isinstance(args, list) else cmd}",
            elapsed_ms=round(elapsed, 2),
        )
    except OSError as exc:
        elapsed = (time.monotonic() - start) * 1000
        return RunResult(
            command=cmd,
            returncode=1,
            stderr=str(exc),
            elapsed_ms=round(elapsed, 2),
        )


def run_background(
    cmd: str | list,
    cwd: str | None = None,
    env: dict | None = None,
) -> int:
    """start a background process, return PID."""
    if isinstance(cmd, str):
        args = shlex.split(cmd)
    else:
        args = cmd

    merged_env = safe_env(env) if env else None
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=cwd,
        env=merged_env,
    )
    _registry[proc.pid] = _TrackedProcess(proc=proc, cmd=cmd)
    return proc.pid


def is_running(pid: int) -> bool:
    """check if a process is still alive."""
    # check tracked registry first
    if pid in _registry:
        return _registry[pid].proc.poll() is None
    # fall back to os-level check
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def kill_process(pid: int, signal_num: int = 15) -> bool:
    """send signal to process. SIGTERM by default. return success."""
    try:
        if pid in _registry:
            _registry[pid].proc.send_signal(signal_num)
        else:
            os.kill(pid, signal_num)
        return True
    except (OSError, ProcessLookupError):
        return False


def wait_for(pid: int, timeout: int = 30) -> RunResult | None:
    """wait for a background process to finish."""
    if pid not in _registry:
        return None

    tracked = _registry[pid]
    start = time.monotonic()
    try:
        stdout, stderr = tracked.proc.communicate(timeout=timeout)
        elapsed = (time.monotonic() - start) * 1000
        result = RunResult(
            command=tracked.cmd,
            returncode=tracked.proc.returncode,
            stdout=stdout or "",
            stderr=stderr or "",
            elapsed_ms=round(elapsed, 2),
        )
        del _registry[pid]
        return result
    except subprocess.TimeoutExpired:
        elapsed = (time.monotonic() - start) * 1000
        return RunResult(
            command=tracked.cmd,
            returncode=-1,
            stderr=f"timed out after {timeout}s",
            elapsed_ms=round(elapsed, 2),
            timed_out=True,
        )


def list_running() -> list[dict]:
    """list all tracked background processes."""
    result = []
    for pid, tracked in list(_registry.items()):
        if tracked.proc.poll() is None:
            result.append({
                "pid": pid,
                "cmd": tracked.cmd,
                "started_at": tracked.started_at.isoformat(),
            })
    return result


def cleanup() -> int:
    """kill all tracked background processes, return count killed."""
    killed = 0
    for pid, tracked in list(_registry.items()):
        if tracked.proc.poll() is None:
            try:
                tracked.proc.send_signal(signal.SIGTERM)
                tracked.proc.wait(timeout=5)
            except (subprocess.TimeoutExpired, OSError):
                try:
                    tracked.proc.kill()
                except OSError:
                    pass
            killed += 1
        del _registry[pid]
    return killed


def which(name: str) -> str | None:
    """find executable on PATH."""
    return shutil.which(name)


def run_pipeline(
    commands: list[str | list],
    cwd: str | None = None,
) -> list[RunResult]:
    """run commands sequentially, stop on first failure."""
    results = []
    for cmd in commands:
        result = run(cmd, cwd=cwd)
        results.append(result)
        if not result.ok:
            break
    return results


def safe_env(extra: dict | None = None) -> dict:
    """return os.environ copy with extra vars, stripping sensitive keys."""
    env = dict(os.environ)
    if extra:
        env.update(extra)
    to_remove = [
        k for k in env
        if any(s in k.lower() for s in _SENSITIVE)
    ]
    for k in to_remove:
        del env[k]
    return env
