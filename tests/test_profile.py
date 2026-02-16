"""tests for profiling and benchmarking."""

import time

from keanu.abilities.world.profile import (
    profile_function, profile_script, benchmark, compare_benchmarks,
    profile_memory, find_slow_functions,
    ProfileResult, BenchmarkResult, MemoryResult, HotSpot,
)


def _slow_func():
    total = 0
    for i in range(10000):
        total += i
    return total


def _fast_func():
    return 42


def _failing_func():
    raise ValueError("boom")


def _allocating_func():
    return [0] * 100000


class TestProfileFunction:

    def test_profiles_callable(self):
        result = profile_function(_slow_func)
        assert result.success
        assert result.hotspots
        assert result.raw_stats

    def test_handles_exception(self):
        result = profile_function(_failing_func)
        assert not result.success
        assert "boom" in result.errors[0]

    def test_hotspots_have_fields(self):
        result = profile_function(_slow_func)
        assert result.success
        for h in result.hotspots:
            assert h.function
            assert h.calls > 0


class TestProfileScript:

    def test_profiles_script(self, tmp_path):
        f = tmp_path / "script.py"
        f.write_text("x = sum(range(1000))\n")
        result = profile_script(str(f))
        assert result.success

    def test_nonexistent_file(self):
        result = profile_script("/nonexistent.py")
        assert not result.success

    def test_syntax_error(self, tmp_path):
        f = tmp_path / "bad.py"
        f.write_text("def broken(:\n")
        result = profile_script(str(f))
        assert not result.success


class TestBenchmark:

    def test_benchmarks_function(self):
        result = benchmark(_fast_func, iterations=10, warmup=2)
        assert result.success
        assert result.iterations == 10
        assert result.avg_time > 0
        assert result.min_time <= result.avg_time
        assert result.max_time >= result.avg_time
        assert result.ops_per_sec > 0

    def test_handles_exception(self):
        result = benchmark(_failing_func, iterations=5, warmup=0)
        assert not result.success

    def test_function_name(self):
        result = benchmark(_fast_func, iterations=5, warmup=1)
        assert result.function_name == "_fast_func"


class TestCompareBenchmarks:

    def test_compare(self):
        slow = BenchmarkResult(success=True, function_name="a",
                               iterations=10, total_time=1.0,
                               avg_time=0.1, min_time=0.08, max_time=0.12)
        fast = BenchmarkResult(success=True, function_name="b",
                               iterations=10, total_time=0.5,
                               avg_time=0.05, min_time=0.04, max_time=0.06)
        comp = compare_benchmarks(slow, fast)
        assert comp["faster"]
        assert comp["speedup"] > 1.0
        assert "faster" in comp["summary"]

    def test_slower(self):
        fast = BenchmarkResult(success=True, function_name="a",
                               iterations=10, total_time=0.5,
                               avg_time=0.05, min_time=0.04, max_time=0.06)
        slow = BenchmarkResult(success=True, function_name="b",
                               iterations=10, total_time=1.0,
                               avg_time=0.1, min_time=0.08, max_time=0.12)
        comp = compare_benchmarks(fast, slow)
        assert not comp["faster"]

    def test_failed_benchmark(self):
        ok = BenchmarkResult(success=True, function_name="a",
                             iterations=10, total_time=1.0, avg_time=0.1,
                             min_time=0.08, max_time=0.12)
        fail = BenchmarkResult(success=False, function_name="b")
        comp = compare_benchmarks(ok, fail)
        assert "error" in comp


class TestProfileMemory:

    def test_profiles_memory(self):
        result = profile_memory(_allocating_func)
        assert result.success
        assert result.peak_mb >= 0

    def test_handles_exception(self):
        result = profile_memory(_failing_func)
        assert not result.success


class TestHotSpot:

    def test_str(self):
        h = HotSpot(function="foo", file="test.py", line=10,
                     total_time=0.5, cum_time=1.0, calls=100,
                     time_per_call=0.005)
        s = str(h)
        assert "foo" in s
        assert "test.py:10" in s
        assert "100 calls" in s
