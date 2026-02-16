"""tests for web lookup ability."""

from unittest.mock import patch, MagicMock

from keanu.abilities.world.lookup import (
    LookupAbility, fetch_url, search_docs, _html_to_text,
    _CACHE, _set_cached, _get_cached, _DOC_SITES,
)


class TestHtmlToText:

    def test_strips_tags(self):
        assert _html_to_text("<p>hello</p>") == "hello"

    def test_strips_scripts(self):
        html = "<script>alert('x')</script><p>safe</p>"
        assert "alert" not in _html_to_text(html)
        assert "safe" in _html_to_text(html)

    def test_strips_styles(self):
        html = "<style>.x{color:red}</style><p>visible</p>"
        assert "color" not in _html_to_text(html)
        assert "visible" in _html_to_text(html)

    def test_decodes_entities(self):
        assert "&amp;" not in _html_to_text("a &amp; b")
        assert "a & b" in _html_to_text("a &amp; b")

    def test_collapses_whitespace(self):
        result = _html_to_text("a\n\n\n\n\nb")
        assert "\n\n\n" not in result


class TestCache:

    def setup_method(self):
        _CACHE.clear()

    def test_set_and_get(self):
        _set_cached("http://example.com", "content")
        assert _get_cached("http://example.com") == "content"

    def test_miss(self):
        assert _get_cached("http://missing.com") is None


class TestFetchUrl:

    def test_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "hello world"
        mock_resp.headers = {"content-type": "text/plain"}
        mock_resp.raise_for_status = lambda: None

        with patch("keanu.abilities.world.lookup.requests.get", return_value=mock_resp):
            result = fetch_url("http://example.com")

        assert result["success"]
        assert "hello world" in result["content"]

    def test_html_stripping(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><body><p>text</p></body></html>"
        mock_resp.headers = {"content-type": "text/html"}
        mock_resp.raise_for_status = lambda: None

        with patch("keanu.abilities.world.lookup.requests.get", return_value=mock_resp):
            result = fetch_url("http://example.com/page")

        assert result["success"]
        assert "<html>" not in result["content"]
        assert "text" in result["content"]

    def test_timeout(self):
        import requests as req
        with patch("keanu.abilities.world.lookup.requests.get",
                   side_effect=req.exceptions.Timeout):
            result = fetch_url("http://slow.com")
        assert not result["success"]
        assert "timeout" in result["content"]

    def test_connection_error(self):
        import requests as req
        with patch("keanu.abilities.world.lookup.requests.get",
                   side_effect=req.exceptions.ConnectionError):
            result = fetch_url("http://down.com")
        assert not result["success"]

    def test_cached(self):
        _CACHE.clear()
        _set_cached("http://cached.com", "cached content")
        result = fetch_url("http://cached.com")
        assert result["success"]
        assert result["cached"]
        assert "cached content" in result["content"]

    def test_max_chars(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "x" * 50000
        mock_resp.headers = {"content-type": "text/plain"}
        mock_resp.raise_for_status = lambda: None

        with patch("keanu.abilities.world.lookup.requests.get", return_value=mock_resp):
            result = fetch_url("http://big.com", max_chars=100)

        assert len(result["content"]) <= 100


class TestSearchDocs:

    def test_search_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = """
        <a class="result__a" href="http://docs.python.org/foo">Python Docs</a>
        <a class="result__snippet">Some snippet text</a>
        """
        mock_resp.raise_for_status = lambda: None

        with patch("keanu.abilities.world.lookup.requests.get", return_value=mock_resp):
            result = search_docs("python list comprehension")

        assert result["success"]

    def test_search_with_site(self):
        mock_resp = MagicMock()
        mock_resp.text = ""
        mock_resp.raise_for_status = lambda: None

        with patch("keanu.abilities.world.lookup.requests.get", return_value=mock_resp) as mock_get:
            search_docs("list comprehension", site="docs.python.org")

        call_args = mock_get.call_args
        assert "site:docs.python.org" in call_args[1]["params"]["q"]

    def test_search_error(self):
        with patch("keanu.abilities.world.lookup.requests.get", side_effect=Exception("nope")):
            result = search_docs("anything")
        assert not result["success"]


class TestDocSites:

    def test_known_sites(self):
        assert "python" in _DOC_SITES
        assert "pytest" in _DOC_SITES
        assert "react" in _DOC_SITES


class TestLookupAbility:

    def test_fetch_url(self):
        ab = LookupAbility()
        mock_resp = MagicMock()
        mock_resp.text = "doc content"
        mock_resp.headers = {"content-type": "text/plain"}
        mock_resp.raise_for_status = lambda: None

        with patch("keanu.abilities.world.lookup.requests.get", return_value=mock_resp):
            result = ab.execute("", context={"url": "http://example.com/api"})

        assert result["success"]
        assert "doc content" in result["result"]

    def test_search_query(self):
        ab = LookupAbility()
        mock_resp = MagicMock()
        mock_resp.text = '<a class="result__a" href="http://r.com">Result</a>'
        mock_resp.raise_for_status = lambda: None

        with patch("keanu.abilities.world.lookup.requests.get", return_value=mock_resp):
            result = ab.execute("", context={"query": "python async"})

        assert result["success"]

    def test_no_args(self):
        ab = LookupAbility()
        result = ab.execute("", context={})
        assert not result["success"]

    def test_library_shortcut(self):
        ab = LookupAbility()
        mock_resp = MagicMock()
        mock_resp.text = ""
        mock_resp.raise_for_status = lambda: None

        with patch("keanu.abilities.world.lookup.requests.get", return_value=mock_resp) as mock_get:
            ab.execute("", context={"query": "async views", "library": "django"})

        call_args = mock_get.call_args
        assert "docs.djangoproject.com" in call_args[1]["params"]["q"]
