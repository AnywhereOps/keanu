"""tests for session caching."""

import ast

from keanu.cache import FileCache, ASTCache, SymbolCache, CacheEntry


class TestCacheEntry:

    def test_defaults(self):
        e = CacheEntry(key="foo", value="bar")
        assert e.hits == 0
        assert e.size == 0


class TestFileCache:

    def test_put_and_get(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1")
        cache = FileCache()
        cache.put(str(f), "x = 1")
        assert cache.get(str(f)) == "x = 1"

    def test_miss_returns_none(self):
        cache = FileCache()
        assert cache.get("/nonexistent/file.py") is None

    def test_invalidate(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1")
        cache = FileCache()
        cache.put(str(f), "x = 1")
        cache.invalidate(str(f))
        assert cache.get(str(f)) is None

    def test_invalidate_all(self, tmp_path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("a")
        f2.write_text("b")
        cache = FileCache()
        cache.put(str(f1), "a")
        cache.put(str(f2), "b")
        cache.invalidate_all()
        assert cache.get(str(f1)) is None
        assert cache.get(str(f2)) is None

    def test_detects_file_change(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1")
        cache = FileCache()
        cache.put(str(f), "x = 1")
        # modify the file
        import time
        time.sleep(0.01)  # ensure mtime changes
        f.write_text("x = 2")
        # cache should miss
        assert cache.get(str(f)) is None

    def test_hit_count(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1")
        cache = FileCache()
        cache.put(str(f), "x = 1")
        cache.get(str(f))
        cache.get(str(f))
        stats = cache.stats()
        assert stats["hits"] == 2

    def test_stats(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("hello")
        cache = FileCache()
        cache.get(str(f))  # miss
        cache.put(str(f), "hello")
        cache.get(str(f))  # hit
        stats = cache.stats()
        assert stats["entries"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

    def test_eviction(self):
        cache = FileCache(max_entries=2)
        # can't test with real files for eviction since we need
        # the hash to match, so just test the mechanism
        cache._entries["a"] = CacheEntry(key="a", value="x", size=1, hits=0, hash="h1")
        cache._entries["b"] = CacheEntry(key="b", value="y", size=1, hits=5, hash="h2")
        cache._total_size = 2
        # evict should remove the one with fewer hits
        cache._evict_lru()
        assert "a" not in cache._entries
        assert "b" in cache._entries

    def test_contains(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x")
        cache = FileCache()
        assert str(f) not in cache
        cache.put(str(f), "x")
        assert str(f) in cache


class TestASTCache:

    def test_parse_and_cache(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1\ndef foo(): pass\n")
        cache = ASTCache()
        tree = cache.parse(str(f))
        assert tree is not None
        assert isinstance(tree, ast.Module)
        # second call should hit cache
        tree2 = cache.parse(str(f))
        assert tree2 is tree

    def test_syntax_error(self, tmp_path):
        f = tmp_path / "bad.py"
        f.write_text("def foo(\n")
        cache = ASTCache()
        tree = cache.parse(str(f))
        assert tree is None

    def test_nonexistent_file(self):
        cache = ASTCache()
        tree = cache.parse("/nonexistent/file.py")
        assert tree is None

    def test_invalidate(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1")
        cache = ASTCache()
        cache.parse(str(f))
        cache.invalidate(str(f))
        # should re-parse on next call
        assert cache.get(str(f)) is None


class TestSymbolCache:

    def test_put_and_get(self):
        cache = SymbolCache()
        cache.put("find:hello", ["result"])
        assert cache.get("find:hello") == ["result"]

    def test_miss(self):
        cache = SymbolCache()
        assert cache.get("find:nope") is None

    def test_mark_dirty(self):
        cache = SymbolCache()
        cache.put("find:hello", ["result"])
        cache.mark_dirty()
        assert cache.get("find:hello") is None

    def test_clear(self):
        cache = SymbolCache()
        cache.put("a", 1)
        cache.put("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None
