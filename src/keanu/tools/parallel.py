"""parallel.py - parallel file operations.

read multiple files at once, run tests in background,
parallel lint+format+test cycles. no LLM needed.

in the world: many hands. the work happens faster when it happens at once.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileReadResult:
    """result of reading a file."""
    path: str
    content: str = ""
    success: bool = True
    error: str = ""
    size_bytes: int = 0


@dataclass
class ParallelResult:
    """result of a parallel operation."""
    results: list = field(default_factory=list)
    duration_s: float = 0.0
    success_count: int = 0
    error_count: int = 0


# ============================================================
# PARALLEL FILE I/O
# ============================================================

def read_files(paths: list[str], max_workers: int = 8) -> ParallelResult:
    """read multiple files in parallel."""
    start = time.time()
    results = []

    def _read_one(path: str) -> FileReadResult:
        try:
            p = Path(path)
            content = p.read_text(errors="replace")
            return FileReadResult(
                path=path, content=content,
                success=True, size_bytes=p.stat().st_size,
            )
        except (OSError, UnicodeDecodeError) as e:
            return FileReadResult(path=path, success=False, error=str(e))

    if len(paths) <= 2:
        results = [_read_one(p) for p in paths]
    else:
        with ThreadPoolExecutor(max_workers=min(max_workers, len(paths))) as pool:
            futures = {pool.submit(_read_one, p): p for p in paths}
            for future in as_completed(futures):
                results.append(future.result())

    # sort back to original order
    path_order = {p: i for i, p in enumerate(paths)}
    results.sort(key=lambda r: path_order.get(r.path, 999))

    return ParallelResult(
        results=results,
        duration_s=time.time() - start,
        success_count=sum(1 for r in results if r.success),
        error_count=sum(1 for r in results if not r.success),
    )


def write_files(file_contents: dict[str, str], max_workers: int = 8) -> ParallelResult:
    """write multiple files in parallel."""
    start = time.time()
    results = []

    def _write_one(path: str, content: str) -> FileReadResult:
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return FileReadResult(path=path, success=True, size_bytes=len(content.encode()))
        except OSError as e:
            return FileReadResult(path=path, success=False, error=str(e))

    if len(file_contents) <= 2:
        results = [_write_one(p, c) for p, c in file_contents.items()]
    else:
        with ThreadPoolExecutor(max_workers=min(max_workers, len(file_contents))) as pool:
            futures = {pool.submit(_write_one, p, c): p for p, c in file_contents.items()}
            for future in as_completed(futures):
                results.append(future.result())

    return ParallelResult(
        results=results,
        duration_s=time.time() - start,
        success_count=sum(1 for r in results if r.success),
        error_count=sum(1 for r in results if not r.success),
    )


# ============================================================
# PARALLEL OPERATIONS
# ============================================================

@dataclass
class OpResult:
    """result of a single operation."""
    name: str
    success: bool = True
    output: str = ""
    error: str = ""
    duration_s: float = 0.0


def run_parallel(operations: dict[str, callable], max_workers: int = 4) -> ParallelResult:
    """run multiple operations in parallel."""
    start = time.time()
    results = []

    def _run_one(name: str, func: callable) -> OpResult:
        op_start = time.time()
        try:
            output = func()
            return OpResult(
                name=name, success=True,
                output=str(output) if output else "",
                duration_s=time.time() - op_start,
            )
        except Exception as e:
            return OpResult(
                name=name, success=False, error=str(e),
                duration_s=time.time() - op_start,
            )

    if len(operations) <= 1:
        for name, func in operations.items():
            results.append(_run_one(name, func))
    else:
        with ThreadPoolExecutor(max_workers=min(max_workers, len(operations))) as pool:
            futures = {pool.submit(_run_one, name, func): name
                       for name, func in operations.items()}
            for future in as_completed(futures):
                results.append(future.result())

    return ParallelResult(
        results=results,
        duration_s=time.time() - start,
        success_count=sum(1 for r in results if r.success),
        error_count=sum(1 for r in results if not r.success),
    )


def lint_format_test(root: str = ".") -> ParallelResult:
    """run lint, format check, and tests in parallel."""
    import subprocess

    def _lint():
        r = subprocess.run(
            ["python3", "-m", "ruff", "check", root],
            capture_output=True, text=True, timeout=60,
        )
        return r.stdout[:500] if r.returncode == 0 else f"FAIL: {r.stdout[:300]}"

    def _format_check():
        r = subprocess.run(
            ["python3", "-m", "ruff", "format", "--check", root],
            capture_output=True, text=True, timeout=60,
        )
        return r.stdout[:500] if r.returncode == 0 else f"FAIL: {r.stdout[:300]}"

    def _test():
        r = subprocess.run(
            ["python3", "-m", "pytest", "--tb=line", "-q", root],
            capture_output=True, text=True, timeout=300,
        )
        return r.stdout[-500:] if r.returncode == 0 else f"FAIL: {r.stdout[-300:]}"

    return run_parallel({
        "lint": _lint,
        "format": _format_check,
        "test": _test,
    })


# ============================================================
# FILE WATCHING
# ============================================================

@dataclass
class WatchEvent:
    """a file change event."""
    path: str
    event_type: str  # created, modified, deleted
    timestamp: float


def watch_files(paths: list[str], callback, interval: float = 1.0,
                max_events: int = 100) -> list[WatchEvent]:
    """watch files for changes and call callback on change.

    simple polling-based watcher. returns events.
    use max_events to limit before returning.
    """
    # snapshot current state
    state: dict[str, float] = {}
    for p in paths:
        path = Path(p)
        if path.exists():
            state[p] = path.stat().st_mtime

    events = []
    while len(events) < max_events:
        time.sleep(interval)
        for p in paths:
            path = Path(p)
            if path.exists():
                mtime = path.stat().st_mtime
                if p not in state:
                    event = WatchEvent(path=p, event_type="created", timestamp=time.time())
                    events.append(event)
                    callback(event)
                elif mtime > state[p]:
                    event = WatchEvent(path=p, event_type="modified", timestamp=time.time())
                    events.append(event)
                    callback(event)
                state[p] = mtime
            elif p in state:
                event = WatchEvent(path=p, event_type="deleted", timestamp=time.time())
                events.append(event)
                callback(event)
                del state[p]

    return events


# ============================================================
# BATCH AST PARSE
# ============================================================

def batch_parse_ast(paths: list[str], max_workers: int = 8) -> dict[str, object]:
    """parse multiple Python files into ASTs in parallel."""
    import ast

    results = {}

    def _parse_one(path: str):
        try:
            source = Path(path).read_text()
            tree = ast.parse(source, filename=path)
            return path, tree
        except (SyntaxError, OSError):
            return path, None

    if len(paths) <= 2:
        for p in paths:
            path, tree = _parse_one(p)
            if tree:
                results[path] = tree
    else:
        with ThreadPoolExecutor(max_workers=min(max_workers, len(paths))) as pool:
            futures = [pool.submit(_parse_one, p) for p in paths]
            for future in as_completed(futures):
                path, tree = future.result()
                if tree:
                    results[path] = tree

    return results
