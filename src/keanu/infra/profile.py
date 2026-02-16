"""profile.py - profiling and benchmarking.

run cProfile on functions, find hotspots, measure memory,
benchmark before/after. no LLM needed.

in the world: the scout. sees where the time goes.
"""

import cProfile
import io
import pstats
import time
import tracemalloc
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class HotSpot:
    """a performance hotspot from profiling."""
    function: str
    file: str
    line: int
    total_time: float    # seconds
    cum_time: float      # cumulative seconds
    calls: int
    time_per_call: float  # seconds per call

    def __str__(self):
        return f"{self.function} ({self.file}:{self.line}) {self.total_time:.4f}s ({self.calls} calls)"


@dataclass
class ProfileResult:
    """result of profiling a function or script."""
    success: bool
    total_time: float = 0.0
    hotspots: list[HotSpot] = field(default_factory=list)
    raw_stats: str = ""
    errors: list[str] = field(default_factory=list)


@dataclass
class BenchmarkResult:
    """result of benchmarking a function."""
    success: bool
    function_name: str = ""
    iterations: int = 0
    total_time: float = 0.0
    avg_time: float = 0.0
    min_time: float = 0.0
    max_time: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def ops_per_sec(self) -> float:
        return 1.0 / self.avg_time if self.avg_time > 0 else 0.0


@dataclass
class MemoryResult:
    """result of memory profiling."""
    success: bool
    peak_mb: float = 0.0
    current_mb: float = 0.0
    top_allocations: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ============================================================
# PROFILING
# ============================================================

def profile_function(func, *args, **kwargs) -> ProfileResult:
    """profile a callable and return hotspots."""
    profiler = cProfile.Profile()
    try:
        profiler.enable()
        func(*args, **kwargs)
        profiler.disable()
    except Exception as e:
        profiler.disable()
        return ProfileResult(success=False, errors=[str(e)])

    # extract stats
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.sort_stats("cumulative")
    stats.print_stats(30)
    raw = stream.getvalue()

    hotspots = _extract_hotspots(stats, limit=20)
    total = sum(h.total_time for h in hotspots[:1]) if hotspots else 0.0

    return ProfileResult(
        success=True,
        total_time=total,
        hotspots=hotspots,
        raw_stats=raw,
    )


def profile_script(filepath: str) -> ProfileResult:
    """profile a Python script file."""
    path = Path(filepath)
    if not path.exists():
        return ProfileResult(success=False, errors=[f"file not found: {filepath}"])

    try:
        code = compile(path.read_text(), filepath, "exec")
    except SyntaxError as e:
        return ProfileResult(success=False, errors=[f"syntax error: {e}"])

    profiler = cProfile.Profile()
    try:
        profiler.enable()
        exec(code, {"__name__": "__main__", "__file__": filepath})
        profiler.disable()
    except Exception as e:
        profiler.disable()
        return ProfileResult(success=False, errors=[str(e)])

    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.sort_stats("cumulative")
    stats.print_stats(30)
    raw = stream.getvalue()

    hotspots = _extract_hotspots(stats, limit=20)
    total = sum(h.total_time for h in hotspots[:1]) if hotspots else 0.0

    return ProfileResult(
        success=True,
        total_time=total,
        hotspots=hotspots,
        raw_stats=raw,
    )


def _extract_hotspots(stats: pstats.Stats, limit: int = 20) -> list[HotSpot]:
    """extract hotspots from pstats."""
    hotspots = []
    # stats.stats is dict of (file, line, func) -> (cc, nc, tt, ct, callers)
    for (file, line, func), (cc, nc, tt, ct, callers) in stats.stats.items():
        if nc == 0:
            continue
        hotspots.append(HotSpot(
            function=func,
            file=file,
            line=line,
            total_time=tt,
            cum_time=ct,
            calls=nc,
            time_per_call=tt / nc if nc else 0,
        ))

    hotspots.sort(key=lambda h: -h.cum_time)
    return hotspots[:limit]


# ============================================================
# BENCHMARKING
# ============================================================

def benchmark(func, *args, iterations: int = 100, warmup: int = 5, **kwargs) -> BenchmarkResult:
    """benchmark a callable."""
    name = getattr(func, "__name__", str(func))

    # warmup
    for _ in range(warmup):
        try:
            func(*args, **kwargs)
        except Exception as e:
            return BenchmarkResult(success=False, function_name=name, errors=[f"warmup failed: {e}"])

    # measure
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        try:
            func(*args, **kwargs)
        except Exception as e:
            return BenchmarkResult(
                success=False, function_name=name,
                iterations=len(times), errors=[str(e)],
            )
        elapsed = time.perf_counter() - start
        times.append(elapsed)

    return BenchmarkResult(
        success=True,
        function_name=name,
        iterations=iterations,
        total_time=sum(times),
        avg_time=sum(times) / len(times),
        min_time=min(times),
        max_time=max(times),
    )


def compare_benchmarks(before: BenchmarkResult, after: BenchmarkResult) -> dict:
    """compare two benchmark results."""
    if not before.success or not after.success:
        return {"error": "one or both benchmarks failed"}

    speedup = before.avg_time / after.avg_time if after.avg_time > 0 else float("inf")
    delta_pct = ((after.avg_time - before.avg_time) / before.avg_time * 100) if before.avg_time > 0 else 0

    return {
        "before_avg": before.avg_time,
        "after_avg": after.avg_time,
        "speedup": speedup,
        "delta_pct": delta_pct,
        "faster": after.avg_time < before.avg_time,
        "summary": (
            f"{speedup:.2f}x {'faster' if speedup > 1 else 'slower'} "
            f"({delta_pct:+.1f}%)"
        ),
    }


# ============================================================
# MEMORY PROFILING
# ============================================================

def profile_memory(func, *args, **kwargs) -> MemoryResult:
    """profile memory usage of a callable."""
    was_tracing = tracemalloc.is_tracing()
    if not was_tracing:
        tracemalloc.start()

    try:
        snapshot_before = tracemalloc.take_snapshot()
        func(*args, **kwargs)
        snapshot_after = tracemalloc.take_snapshot()
    except Exception as e:
        if not was_tracing:
            tracemalloc.stop()
        return MemoryResult(success=False, errors=[str(e)])

    current, peak = tracemalloc.get_traced_memory()

    # top allocations (diff)
    top_stats = snapshot_after.compare_to(snapshot_before, "lineno")
    top_allocs = []
    for stat in top_stats[:10]:
        if stat.size_diff > 0:
            top_allocs.append({
                "file": str(stat.traceback),
                "size_kb": stat.size_diff / 1024,
                "count": stat.count_diff,
            })

    if not was_tracing:
        tracemalloc.stop()

    return MemoryResult(
        success=True,
        peak_mb=peak / (1024 * 1024),
        current_mb=current / (1024 * 1024),
        top_allocations=top_allocs,
    )


# ============================================================
# FILE-BASED PROFILING
# ============================================================

def find_slow_functions(filepath: str, threshold_ms: float = 10.0) -> list[HotSpot]:
    """find functions in a module that are slow."""
    result = profile_script(filepath)
    if not result.success:
        return []
    return [h for h in result.hotspots if h.total_time * 1000 >= threshold_ms]


def find_memory_hogs(filepath: str, threshold_kb: float = 100.0) -> list[dict]:
    """find functions that allocate a lot of memory."""
    path = Path(filepath)
    if not path.exists():
        return []

    try:
        code = compile(path.read_text(), filepath, "exec")
    except SyntaxError:
        return []

    tracemalloc.start()
    try:
        exec(code, {"__name__": "__main__", "__file__": filepath})
    except Exception:
        pass
    snapshot = tracemalloc.take_snapshot()
    tracemalloc.stop()

    hogs = []
    for stat in snapshot.statistics("lineno")[:20]:
        if stat.size / 1024 >= threshold_kb:
            hogs.append({
                "file": str(stat.traceback),
                "size_kb": stat.size / 1024,
                "count": stat.count,
            })
    return hogs
