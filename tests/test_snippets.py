"""tests for code snippet management."""

from unittest.mock import patch

from keanu.gen.snippets import (
    Snippet, save_snippet, get_snippet, delete_snippet,
    list_snippets, use_snippet, search_snippets, rebuild_index,
)


class TestSnippet:

    def test_defaults(self):
        s = Snippet(name="test", content="x = 1")
        assert s.created_at > 0
        assert s.used_count == 0

    def test_to_dict(self):
        s = Snippet(name="test", content="x = 1", language="python", tags=["util"])
        d = s.to_dict()
        assert d["name"] == "test"
        assert d["language"] == "python"

    def test_from_dict(self):
        d = {"name": "test", "content": "x = 1", "language": "python"}
        s = Snippet.from_dict(d)
        assert s.name == "test"
        assert s.content == "x = 1"


class TestSaveLoad:

    def test_save_and_get(self, tmp_path):
        snippets_dir = tmp_path / "snippets"
        with patch("keanu.gen.snippets._SNIPPETS_DIR", snippets_dir):
            with patch("keanu.gen.snippets._SNIPPETS_INDEX", snippets_dir / "index.json"):
                s = Snippet(name="hello", content="print('hello')", language="python")
                save_snippet(s)
                loaded = get_snippet("hello")
                assert loaded.content == "print('hello')"
                assert loaded.language == "python"

    def test_get_missing(self, tmp_path):
        snippets_dir = tmp_path / "snippets"
        with patch("keanu.gen.snippets._SNIPPETS_DIR", snippets_dir):
            try:
                get_snippet("nonexistent")
                assert False
            except FileNotFoundError:
                pass

    def test_delete(self, tmp_path):
        snippets_dir = tmp_path / "snippets"
        with patch("keanu.gen.snippets._SNIPPETS_DIR", snippets_dir):
            with patch("keanu.gen.snippets._SNIPPETS_INDEX", snippets_dir / "index.json"):
                save_snippet(Snippet(name="temp", content="x"))
                assert delete_snippet("temp")
                assert not delete_snippet("temp")

    def test_overwrite(self, tmp_path):
        snippets_dir = tmp_path / "snippets"
        with patch("keanu.gen.snippets._SNIPPETS_DIR", snippets_dir):
            with patch("keanu.gen.snippets._SNIPPETS_INDEX", snippets_dir / "index.json"):
                save_snippet(Snippet(name="test", content="v1"))
                save_snippet(Snippet(name="test", content="v2"))
                loaded = get_snippet("test")
                assert loaded.content == "v2"


class TestListSnippets:

    def test_list_all(self, tmp_path):
        snippets_dir = tmp_path / "snippets"
        with patch("keanu.gen.snippets._SNIPPETS_DIR", snippets_dir):
            with patch("keanu.gen.snippets._SNIPPETS_INDEX", snippets_dir / "index.json"):
                save_snippet(Snippet(name="a", content="1", tags=["util"]))
                save_snippet(Snippet(name="b", content="2", tags=["web"]))
                result = list_snippets()
                assert len(result) == 2

    def test_filter_by_tag(self, tmp_path):
        snippets_dir = tmp_path / "snippets"
        with patch("keanu.gen.snippets._SNIPPETS_DIR", snippets_dir):
            with patch("keanu.gen.snippets._SNIPPETS_INDEX", snippets_dir / "index.json"):
                save_snippet(Snippet(name="a", content="1", tags=["util"]))
                save_snippet(Snippet(name="b", content="2", tags=["web"]))
                result = list_snippets(tag="web")
                assert len(result) == 1

    def test_filter_by_language(self, tmp_path):
        snippets_dir = tmp_path / "snippets"
        with patch("keanu.gen.snippets._SNIPPETS_DIR", snippets_dir):
            with patch("keanu.gen.snippets._SNIPPETS_INDEX", snippets_dir / "index.json"):
                save_snippet(Snippet(name="a", content="1", language="python"))
                save_snippet(Snippet(name="b", content="2", language="go"))
                result = list_snippets(language="python")
                assert len(result) == 1


class TestUseSnippet:

    def test_increments_count(self, tmp_path):
        snippets_dir = tmp_path / "snippets"
        with patch("keanu.gen.snippets._SNIPPETS_DIR", snippets_dir):
            with patch("keanu.gen.snippets._SNIPPETS_INDEX", snippets_dir / "index.json"):
                save_snippet(Snippet(name="test", content="x"))
                use_snippet("test")
                use_snippet("test")
                loaded = get_snippet("test")
                assert loaded.used_count == 2


class TestSearchSnippets:

    def test_search_by_name(self, tmp_path):
        snippets_dir = tmp_path / "snippets"
        with patch("keanu.gen.snippets._SNIPPETS_DIR", snippets_dir):
            with patch("keanu.gen.snippets._SNIPPETS_INDEX", snippets_dir / "index.json"):
                save_snippet(Snippet(name="hello_world", content="print('hi')"))
                save_snippet(Snippet(name="goodbye", content="print('bye')"))
                results = search_snippets("hello")
                assert len(results) >= 1
                assert results[0].name == "hello_world"

    def test_search_by_content(self, tmp_path):
        snippets_dir = tmp_path / "snippets"
        with patch("keanu.gen.snippets._SNIPPETS_DIR", snippets_dir):
            with patch("keanu.gen.snippets._SNIPPETS_INDEX", snippets_dir / "index.json"):
                save_snippet(Snippet(name="a", content="import requests"))
                results = search_snippets("requests")
                assert len(results) >= 1

    def test_search_no_results(self, tmp_path):
        snippets_dir = tmp_path / "snippets"
        with patch("keanu.gen.snippets._SNIPPETS_DIR", snippets_dir):
            results = search_snippets("nothing")
            assert results == []


class TestRebuildIndex:

    def test_rebuild(self, tmp_path):
        snippets_dir = tmp_path / "snippets"
        with patch("keanu.gen.snippets._SNIPPETS_DIR", snippets_dir):
            with patch("keanu.gen.snippets._SNIPPETS_INDEX", snippets_dir / "index.json"):
                save_snippet(Snippet(name="a", content="1"))
                save_snippet(Snippet(name="b", content="2"))
                # delete index
                (snippets_dir / "index.json").unlink()
                count = rebuild_index()
                assert count == 2

    def test_empty(self, tmp_path):
        with patch("keanu.gen.snippets._SNIPPETS_DIR", tmp_path / "empty"):
            assert rebuild_index() == 0
