"""tests for codebase-aware RAG."""

import json
from pathlib import Path
from unittest.mock import patch

from keanu.data.rag import (
    chunk_file, discover_files, file_hash,
    build_index, incremental_index, search, keyword_search, hybrid_search,
    get_index_stats, Chunk, SearchResult, IndexStats,
    _chunk_python, _chunk_markdown, _chunk_fixed,
    _store_json, _load_json_chunks, _save_meta, _load_meta,
)


class TestChunk:

    def test_auto_hash(self):
        c = Chunk(file_path="test.py", content="hello", start_line=1, end_line=5)
        assert c.hash
        assert len(c.hash) == 16

    def test_id_format(self):
        c = Chunk(file_path="test.py", content="hello", start_line=1, end_line=5)
        assert c.id.startswith("test.py:1-5:")


class TestChunkPython:

    def test_function_boundaries(self, tmp_path):
        code = """import os

def foo():
    return 1

def bar():
    return 2

class Baz:
    pass
"""
        f = tmp_path / "test.py"
        f.write_text(code)
        chunks = chunk_file(str(f))
        assert len(chunks) >= 3

    def test_single_function(self, tmp_path):
        f = tmp_path / "small.py"
        f.write_text("def hello():\n    return 'hi'\n")
        chunks = chunk_file(str(f))
        assert len(chunks) >= 1
        assert "hello" in chunks[0].content

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.py"
        f.write_text("")
        chunks = chunk_file(str(f))
        assert len(chunks) == 0

    def test_max_chunk_size(self, tmp_path):
        f = tmp_path / "big.py"
        lines = [f"x_{i} = {i}" for i in range(100)]
        f.write_text("\n".join(lines))
        chunks = chunk_file(str(f), max_chunk_lines=20)
        assert len(chunks) >= 5


class TestChunkMarkdown:

    def test_header_boundaries(self, tmp_path):
        md = """# Title

Some intro text.

## Section 1

Content here.

## Section 2

More content.
"""
        f = tmp_path / "test.md"
        f.write_text(md)
        chunks = chunk_file(str(f))
        assert len(chunks) >= 2
        assert chunks[0].chunk_type == "markdown"

    def test_single_section(self, tmp_path):
        f = tmp_path / "one.md"
        f.write_text("# Just one section\n\nSome text.\n")
        chunks = chunk_file(str(f))
        assert len(chunks) == 1


class TestChunkFixed:

    def test_json_file(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text('{"key": "value"}\n')
        chunks = chunk_file(str(f))
        assert len(chunks) >= 1


class TestDiscoverFiles:

    def test_finds_python(self, tmp_path):
        (tmp_path / "main.py").write_text("x = 1\n")
        (tmp_path / "readme.md").write_text("# hi\n")
        files = discover_files(str(tmp_path))
        assert any("main.py" in f for f in files)
        assert any("readme.md" in f for f in files)

    def test_skips_pycache(self, tmp_path):
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "mod.pyc").write_text("binary")
        (tmp_path / "main.py").write_text("x = 1\n")
        files = discover_files(str(tmp_path))
        assert not any("__pycache__" in f for f in files)

    def test_skips_binary(self, tmp_path):
        (tmp_path / "image.png").write_text("not really")
        (tmp_path / "main.py").write_text("x = 1\n")
        files = discover_files(str(tmp_path))
        assert not any("image.png" in f for f in files)

    def test_empty_dir(self, tmp_path):
        assert discover_files(str(tmp_path)) == []


class TestFileHash:

    def test_consistent(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        h1 = file_hash(str(f))
        h2 = file_hash(str(f))
        assert h1 == h2

    def test_different_content(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        h1 = file_hash(str(f))
        f.write_text("world")
        h2 = file_hash(str(f))
        assert h1 != h2

    def test_missing_file(self):
        assert file_hash("/nonexistent") == ""


class TestBuildIndex:

    def test_builds_index(self, tmp_path):
        rag_dir = tmp_path / "rag"
        (tmp_path / "project" / "src").mkdir(parents=True)
        (tmp_path / "project" / "src" / "main.py").write_text("def hello(): pass\n")

        with patch("keanu.data.rag._RAG_DIR", rag_dir):
            with patch("keanu.data.rag._INDEX_META", rag_dir / "meta.json"):
                stats = build_index(str(tmp_path / "project"))
                assert stats.total_files >= 1
                assert stats.total_chunks >= 1

    def test_empty_project(self, tmp_path):
        rag_dir = tmp_path / "rag"
        project = tmp_path / "empty"
        project.mkdir()

        with patch("keanu.data.rag._RAG_DIR", rag_dir):
            with patch("keanu.data.rag._INDEX_META", rag_dir / "meta.json"):
                stats = build_index(str(project))
                assert stats.total_files == 0


class TestIncrementalIndex:

    def test_incremental(self, tmp_path):
        rag_dir = tmp_path / "rag"
        project = tmp_path / "project"
        project.mkdir()
        (project / "a.py").write_text("x = 1\n")

        with patch("keanu.data.rag._RAG_DIR", rag_dir):
            with patch("keanu.data.rag._INDEX_META", rag_dir / "meta.json"):
                # first index
                build_index(str(project))

                # modify a file
                (project / "a.py").write_text("x = 2\ny = 3\n")

                # incremental should pick up change
                stats = incremental_index(str(project))
                assert stats.total_chunks >= 1

    def test_no_changes(self, tmp_path):
        rag_dir = tmp_path / "rag"
        project = tmp_path / "project"
        project.mkdir()
        (project / "a.py").write_text("x = 1\n")

        with patch("keanu.data.rag._RAG_DIR", rag_dir):
            with patch("keanu.data.rag._INDEX_META", rag_dir / "meta.json"):
                build_index(str(project))
                stats = incremental_index(str(project))
                # no new chunks needed
                assert stats.total_files >= 1


class TestKeywordSearch:

    def test_finds_match(self, tmp_path):
        rag_dir = tmp_path / "rag"
        rag_dir.mkdir(parents=True)
        chunks = [
            {"file_path": "a.py", "content": "def hello_world(): pass",
             "start_line": 1, "end_line": 1, "chunk_type": "code", "hash": "abc"},
            {"file_path": "b.py", "content": "def goodbye(): pass",
             "start_line": 1, "end_line": 1, "chunk_type": "code", "hash": "def"},
        ]
        (rag_dir / "chunks.json").write_text(json.dumps(chunks))

        with patch("keanu.data.rag._RAG_DIR", rag_dir):
            results = keyword_search("hello")
            assert len(results) >= 1
            assert "hello" in results[0].chunk.content

    def test_no_match(self, tmp_path):
        rag_dir = tmp_path / "rag"
        rag_dir.mkdir(parents=True)
        (rag_dir / "chunks.json").write_text(json.dumps([
            {"file_path": "a.py", "content": "xyz", "start_line": 1, "end_line": 1, "hash": "a"},
        ]))

        with patch("keanu.data.rag._RAG_DIR", rag_dir):
            results = keyword_search("nothere")
            assert len(results) == 0

    def test_empty_index(self, tmp_path):
        with patch("keanu.data.rag._RAG_DIR", tmp_path / "rag"):
            results = keyword_search("anything")
            assert results == []


class TestJsonStore:

    def test_store_and_load(self, tmp_path):
        rag_dir = tmp_path / "rag"
        chunks = [
            Chunk("a.py", "content", 1, 5),
            Chunk("b.py", "more", 1, 3),
        ]

        with patch("keanu.data.rag._RAG_DIR", rag_dir):
            _store_json(chunks, ".")
            loaded = _load_json_chunks()
            assert len(loaded) == 2

    def test_incremental_store(self, tmp_path):
        rag_dir = tmp_path / "rag"
        initial = [Chunk("a.py", "old", 1, 5)]
        update = [Chunk("a.py", "new", 1, 5)]

        with patch("keanu.data.rag._RAG_DIR", rag_dir):
            _store_json(initial, ".")
            _store_json(update, ".", incremental=True)
            loaded = _load_json_chunks()
            assert len(loaded) == 1
            assert loaded[0]["content"] == "new"


class TestMeta:

    def test_save_load(self, tmp_path):
        rag_dir = tmp_path / "rag"
        meta_file = rag_dir / "meta.json"

        with patch("keanu.data.rag._RAG_DIR", rag_dir):
            with patch("keanu.data.rag._INDEX_META", meta_file):
                _save_meta({"files": 10, "chunks": 50})
                loaded = _load_meta()
                assert loaded["files"] == 10

    def test_load_missing(self, tmp_path):
        with patch("keanu.data.rag._INDEX_META", tmp_path / "nope.json"):
            assert _load_meta() == {}


class TestIndexStats:

    def test_get_stats(self, tmp_path):
        rag_dir = tmp_path / "rag"
        meta_file = rag_dir / "meta.json"
        rag_dir.mkdir()
        meta_file.write_text(json.dumps({"files": 5, "chunks": 20, "indexed_at": 1000}))

        with patch("keanu.data.rag._RAG_DIR", rag_dir):
            with patch("keanu.data.rag._INDEX_META", meta_file):
                stats = get_index_stats()
                assert stats.total_files == 5
                assert stats.total_chunks == 20
