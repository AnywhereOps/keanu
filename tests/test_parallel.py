"""tests for parallel file operations."""

import ast

from keanu.tools.parallel import (
    read_files, write_files, run_parallel, batch_parse_ast,
    FileReadResult, ParallelResult, OpResult,
)


class TestReadFiles:

    def test_reads_multiple(self, tmp_path):
        (tmp_path / "a.txt").write_text("hello")
        (tmp_path / "b.txt").write_text("world")
        result = read_files([str(tmp_path / "a.txt"), str(tmp_path / "b.txt")])
        assert result.success_count == 2
        assert result.error_count == 0
        assert result.results[0].content == "hello"
        assert result.results[1].content == "world"

    def test_preserves_order(self, tmp_path):
        for i in range(5):
            (tmp_path / f"f{i}.txt").write_text(f"content {i}")
        paths = [str(tmp_path / f"f{i}.txt") for i in range(5)]
        result = read_files(paths)
        assert result.success_count == 5
        for i, r in enumerate(result.results):
            assert r.content == f"content {i}"

    def test_handles_missing_files(self, tmp_path):
        (tmp_path / "exists.txt").write_text("yes")
        result = read_files([str(tmp_path / "exists.txt"), "/nonexistent/file.txt"])
        assert result.success_count == 1
        assert result.error_count == 1

    def test_empty_list(self):
        result = read_files([])
        assert result.success_count == 0

    def test_single_file(self, tmp_path):
        (tmp_path / "one.txt").write_text("solo")
        result = read_files([str(tmp_path / "one.txt")])
        assert result.success_count == 1
        assert result.results[0].content == "solo"


class TestWriteFiles:

    def test_writes_multiple(self, tmp_path):
        files = {
            str(tmp_path / "a.txt"): "hello",
            str(tmp_path / "b.txt"): "world",
        }
        result = write_files(files)
        assert result.success_count == 2
        assert (tmp_path / "a.txt").read_text() == "hello"
        assert (tmp_path / "b.txt").read_text() == "world"

    def test_creates_directories(self, tmp_path):
        files = {str(tmp_path / "sub" / "deep" / "file.txt"): "nested"}
        result = write_files(files)
        assert result.success_count == 1
        assert (tmp_path / "sub" / "deep" / "file.txt").read_text() == "nested"

    def test_empty(self):
        result = write_files({})
        assert result.success_count == 0


class TestRunParallel:

    def test_runs_multiple_ops(self):
        ops = {
            "add": lambda: 2 + 2,
            "mul": lambda: 3 * 3,
        }
        result = run_parallel(ops)
        assert result.success_count == 2

    def test_handles_errors(self):
        ops = {
            "good": lambda: "ok",
            "bad": lambda: 1 / 0,
        }
        result = run_parallel(ops)
        assert result.success_count == 1
        assert result.error_count == 1

    def test_single_op(self):
        result = run_parallel({"solo": lambda: 42})
        assert result.success_count == 1

    def test_empty(self):
        result = run_parallel({})
        assert result.success_count == 0


class TestBatchParseAst:

    def test_parses_multiple(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.py").write_text("def foo(): pass\n")
        results = batch_parse_ast([str(tmp_path / "a.py"), str(tmp_path / "b.py")])
        assert len(results) == 2
        for path, tree in results.items():
            assert isinstance(tree, ast.Module)

    def test_skips_syntax_errors(self, tmp_path):
        (tmp_path / "good.py").write_text("x = 1\n")
        (tmp_path / "bad.py").write_text("def broken(:\n")
        results = batch_parse_ast([str(tmp_path / "good.py"), str(tmp_path / "bad.py")])
        assert len(results) == 1

    def test_empty(self):
        results = batch_parse_ast([])
        assert results == {}


class TestDataclasses:

    def test_file_read_result(self):
        r = FileReadResult(path="test.py", content="hello", size_bytes=5)
        assert r.success
        assert r.size_bytes == 5

    def test_parallel_result(self):
        r = ParallelResult(results=[1, 2], success_count=2, error_count=0, duration_s=0.1)
        assert r.success_count == 2

    def test_op_result(self):
        r = OpResult(name="test", success=True, output="ok", duration_s=0.05)
        assert r.success
        assert r.output == "ok"
