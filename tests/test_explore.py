"""Tests for the explore ability: ingest, retrieve, search, RAG."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from keanu.abilities.seeing.explore import ExploreAbility
from keanu.abilities.seeing.explore.ingest import (
    ingest, ingest_file, SUPPORTED_EXTENSIONS, _get_converter, _get_splitter,
)
from keanu.abilities.seeing.explore.retrieve import (
    retrieve, build_context,
)
from keanu.abilities.seeing.explore.search import (
    web_search, _fetch_page, _strip_html,
)


# ============================================================
# ABILITY REGISTRATION
# ============================================================

class TestExploreAbility:

    def test_registered(self):
        from keanu.abilities import _REGISTRY
        assert "explore" in _REGISTRY

    def test_can_handle_ingest(self):
        ab = ExploreAbility()
        can, conf = ab.can_handle("ingest this directory")
        assert can is True
        assert conf >= 0.8

    def test_can_handle_rag(self):
        ab = ExploreAbility()
        can, conf = ab.can_handle("search for relevant context")
        assert can is True

    def test_can_handle_search_for(self):
        ab = ExploreAbility()
        can, conf = ab.can_handle("search for haystack docs")
        assert can is True

    def test_no_match_on_unrelated(self):
        ab = ExploreAbility()
        can, conf = ab.can_handle("write a poem about dogs")
        assert can is False


# ============================================================
# CONVERTERS + SPLITTER
# ============================================================

class TestConverters:

    def test_unsupported_extension(self):
        result = _get_converter(".xyz")
        assert result is None

    def test_supported_extensions_all_have_converters(self):
        for ext in SUPPORTED_EXTENSIONS:
            converter_name = SUPPORTED_EXTENSIONS[ext]
            assert converter_name in (
                "PyPDFToDocument", "HTMLToDocument",
                "MarkdownToDocument", "TextFileToDocument",
            ), f"Unknown converter for {ext}"

    def test_pdf_converter(self):
        converter = _get_converter(".pdf")
        assert converter is not None

    def test_markdown_converter(self):
        converter = _get_converter(".md")
        assert converter is not None

    def test_text_converter(self):
        converter = _get_converter(".py")
        assert converter is not None

    def test_html_converter(self):
        converter = _get_converter(".html")
        assert converter is not None

    def test_splitter_creates(self):
        splitter = _get_splitter()
        assert splitter is not None


# ============================================================
# INGEST
# ============================================================

class TestIngest:

    def test_missing_file(self):
        result = ingest_file("/nonexistent/file.txt")
        assert result is None

    def test_missing_path(self):
        result = ingest("/nonexistent/path")
        assert result["files"] == 0
        assert result["chunks"] == 0

    @patch("keanu.abilities.seeing.explore.ingest._store_chunks")
    @patch("keanu.abilities.seeing.explore.ingest._get_splitter")
    @patch("keanu.abilities.seeing.explore.ingest._get_converter")
    def test_ingest_single_file(self, mock_converter, mock_splitter, mock_store, tmp_path):
        test_file = tmp_path / "test.md"
        test_file.write_text("# Hello\n\nTest content here.")

        mock_doc = MagicMock()
        mock_doc.content = "Test content here."
        mock_doc.meta = {}

        mock_conv_instance = MagicMock()
        mock_conv_instance.run.return_value = {"documents": [mock_doc]}
        mock_converter.return_value = mock_conv_instance

        mock_split_instance = MagicMock()
        mock_split_instance.run.return_value = {"documents": [mock_doc]}
        mock_splitter.return_value = mock_split_instance

        mock_store.return_value = 1

        result = ingest_file(str(test_file))
        assert result is not None
        assert result["chunks"] == 1
        mock_store.assert_called_once()

    @patch("keanu.abilities.seeing.explore.ingest.ingest_file")
    def test_ingest_directory(self, mock_ingest_file, tmp_path):
        (tmp_path / "a.md").write_text("Doc A")
        (tmp_path / "b.py").write_text("Doc B")
        (tmp_path / "c.xyz").write_text("Unsupported")

        mock_ingest_file.return_value = {"file": "test", "chunks": 3, "collection": "keanu_rag"}

        result = ingest(str(tmp_path))
        # should call ingest_file for .md and .py, not .xyz
        assert result["files"] >= 2
        assert result["chunks"] >= 6

    @patch("keanu.abilities.seeing.explore.ingest.ingest_file")
    def test_ingest_skips_pycache(self, mock_ingest_file, tmp_path):
        cache_dir = tmp_path / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "cached.py").write_text("cached file")
        (tmp_path / "real.py").write_text("real file")

        mock_ingest_file.return_value = {"file": "test", "chunks": 1, "collection": "keanu_rag"}

        result = ingest(str(tmp_path))
        # should only ingest real.py, not __pycache__/cached.py
        assert mock_ingest_file.call_count == 1


# ============================================================
# RETRIEVE
# ============================================================

class TestRetrieve:

    @patch("keanu.abilities.seeing.explore.retrieve.draw")
    def test_no_collection(self, mock_draw):
        mock_draw.return_value = None
        result = retrieve("test query")
        assert result == []

    @patch("keanu.abilities.seeing.explore.retrieve.draw")
    def test_with_results(self, mock_draw):
        mock_coll = MagicMock()
        mock_coll.query.return_value = {
            "documents": [["chunk 1", "chunk 2"]],
            "metadatas": [[
                {"source": "/a.md", "chunk_index": 0},
                {"source": "/b.md", "chunk_index": 1},
            ]],
            "distances": [[0.1, 0.3]],
        }
        mock_draw.return_value = mock_coll

        result = retrieve("test query", n_results=2)
        assert len(result) == 2
        assert result[0]["content"] == "chunk 1"
        assert result[0]["distance"] == 0.1
        assert result[1]["source"] == "/b.md"

    @patch("keanu.abilities.seeing.explore.retrieve.draw")
    def test_empty_results(self, mock_draw):
        mock_coll = MagicMock()
        mock_coll.query.return_value = {
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
        }
        mock_draw.return_value = mock_coll

        result = retrieve("nothing")
        assert result == []


class TestBuildContext:

    @patch("keanu.abilities.seeing.explore.retrieve.retrieve")
    def test_builds_context_block(self, mock_retrieve):
        mock_retrieve.return_value = [
            {"content": "first chunk", "source": "/a.md", "distance": 0.1, "chunk_index": 0},
            {"content": "second chunk", "source": "/b.md", "distance": 0.2, "chunk_index": 0},
        ]
        ctx = build_context("test query")
        assert "[CONTEXT" in ctx
        assert "first chunk" in ctx
        assert "second chunk" in ctx
        assert "[END CONTEXT]" in ctx

    @patch("keanu.abilities.seeing.explore.retrieve.retrieve")
    def test_empty_context(self, mock_retrieve):
        mock_retrieve.return_value = []
        ctx = build_context("test query")
        assert ctx == ""

    @patch("keanu.abilities.seeing.explore.search.web_search")
    @patch("keanu.abilities.seeing.explore.retrieve.retrieve")
    def test_context_with_web(self, mock_retrieve, mock_web):
        mock_retrieve.return_value = [
            {"content": "doc chunk", "source": "/a.md", "distance": 0.1, "chunk_index": 0},
        ]
        mock_web.return_value = [
            {"url": "https://example.com", "title": "Ex", "snippet": "web content", "content": "web content"},
        ]
        ctx = build_context("test query", include_web=True)
        assert "doc chunk" in ctx
        assert "web content" in ctx


# ============================================================
# WEB SEARCH
# ============================================================

class TestWebSearch:

    def test_no_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            results = web_search("test query")
            assert results == []

    @patch("keanu.abilities.seeing.explore.search.requests.post")
    def test_search_with_key(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "organic": [
                {"link": "https://example.com", "title": "Example", "snippet": "A test"},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        with patch("keanu.abilities.seeing.explore.search._fetch_page", return_value="page content"):
            with patch.dict("os.environ", {"SERPER_API_KEY": "test-key"}):
                results = web_search("test query")

        assert len(results) == 1
        assert results[0]["url"] == "https://example.com"

    @patch("keanu.abilities.seeing.explore.search.requests.post")
    def test_search_error_returns_empty(self, mock_post):
        mock_post.side_effect = Exception("network error")
        with patch.dict("os.environ", {"SERPER_API_KEY": "test-key"}):
            results = web_search("test query")
        assert results == []


class TestStripHtml:

    def test_strips_tags(self):
        result = _strip_html("<p>Hello <b>world</b></p>")
        assert "Hello" in result
        assert "world" in result
        assert "<" not in result

    def test_strips_scripts(self):
        result = _strip_html("<script>alert('x')</script><p>Content</p>")
        assert "alert" not in result
        assert "Content" in result


class TestFetchPage:

    @patch("keanu.abilities.seeing.explore.search.requests.get")
    def test_fetch_html(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.text = "<html><body><p>Hello world</p></body></html>"
        mock_resp.headers = {"content-type": "text/html"}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        text = _fetch_page("https://example.com")
        assert "Hello world" in text

    @patch("keanu.abilities.seeing.explore.search.requests.get")
    def test_fetch_error_returns_none(self, mock_get):
        mock_get.side_effect = Exception("timeout")
        text = _fetch_page("https://example.com")
        assert text is None
