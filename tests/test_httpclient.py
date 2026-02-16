"""Tests for httpclient.py - HTTP client wrapper over urllib."""

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

from keanu.tools.httpclient import (
    RequestConfig,
    Response,
    build_url,
    delete,
    format_curl,
    get,
    is_error,
    is_redirect,
    is_success,
    parse_json_response,
    post,
    put,
    _retry_request,
)


# ============================================================
# build_url
# ============================================================

class TestBuildUrl:
    def test_base_only(self):
        assert build_url("https://api.example.com") == "https://api.example.com"

    def test_base_with_path(self):
        assert build_url("https://api.example.com", "/v1/chat") == "https://api.example.com/v1/chat"

    def test_strips_trailing_slash(self):
        assert build_url("https://api.example.com/", "v1") == "https://api.example.com/v1"

    def test_with_params(self):
        url = build_url("https://x.com", params={"q": "hello", "n": "5"})
        assert "q=hello" in url
        assert "n=5" in url
        assert "?" in url

    def test_params_appended_with_ampersand_when_query_exists(self):
        url = build_url("https://x.com?a=1", params={"b": "2"})
        assert "a=1&b=2" in url

    def test_path_and_params(self):
        url = build_url("https://x.com", "/search", {"q": "test"})
        assert url.startswith("https://x.com/search?")
        assert "q=test" in url


# ============================================================
# Response
# ============================================================

class TestResponse:
    def test_creation(self):
        r = Response(status=200, headers={}, body='{"ok":true}',
                     json_body={"ok": True}, elapsed_ms=12.5,
                     url="https://x.com")
        assert r.status == 200
        assert r.json_body == {"ok": True}

    def test_json_body_none(self):
        r = Response(status=200, headers={}, body="not json",
                     json_body=None, elapsed_ms=1.0, url="https://x.com")
        assert r.json_body is None


# ============================================================
# RequestConfig
# ============================================================

class TestRequestConfig:
    def test_defaults(self):
        c = RequestConfig()
        assert c.timeout == 30
        assert c.retries == 0
        assert c.retry_delay == 1.0
        assert c.headers == {}
        assert c.follow_redirects is True
        assert c.verify_ssl is True

    def test_custom(self):
        c = RequestConfig(timeout=10, retries=3, verify_ssl=False)
        assert c.timeout == 10
        assert c.retries == 3
        assert c.verify_ssl is False


# ============================================================
# status helpers
# ============================================================

class TestStatusHelpers:
    def _resp(self, status):
        return Response(status=status, headers={}, body="",
                        json_body=None, elapsed_ms=0, url="")

    def test_is_success(self):
        assert is_success(self._resp(200)) is True
        assert is_success(self._resp(201)) is True
        assert is_success(self._resp(299)) is True
        assert is_success(self._resp(300)) is False
        assert is_success(self._resp(404)) is False

    def test_is_redirect(self):
        assert is_redirect(self._resp(301)) is True
        assert is_redirect(self._resp(302)) is True
        assert is_redirect(self._resp(200)) is False
        assert is_redirect(self._resp(400)) is False

    def test_is_error(self):
        assert is_error(self._resp(400)) is True
        assert is_error(self._resp(404)) is True
        assert is_error(self._resp(500)) is True
        assert is_error(self._resp(200)) is False
        assert is_error(self._resp(301)) is False


# ============================================================
# parse_json_response
# ============================================================

class TestParseJson:
    def test_valid_json(self):
        r = Response(status=200, headers={}, body='{"a":1}',
                     json_body=None, elapsed_ms=0, url="https://x.com")
        assert parse_json_response(r) == {"a": 1}

    def test_invalid_json_raises(self):
        r = Response(status=200, headers={}, body="nope",
                     json_body=None, elapsed_ms=0, url="https://x.com")
        try:
            parse_json_response(r)
            assert False, "should have raised"
        except ValueError as exc:
            assert "failed to parse" in str(exc)


# ============================================================
# format_curl
# ============================================================

class TestFormatCurl:
    def test_simple_get(self):
        cmd = format_curl("GET", "https://x.com/api")
        assert cmd == "curl -X GET 'https://x.com/api'"

    def test_post_with_data(self):
        cmd = format_curl("POST", "https://x.com/api", data={"key": "val"})
        assert "-X POST" in cmd
        assert "-d" in cmd
        assert "key" in cmd

    def test_custom_headers(self):
        cmd = format_curl("GET", "https://x.com", headers={"Authorization": "Bearer tok"})
        assert "-H 'Authorization: Bearer tok'" in cmd

    def test_headers_sorted(self):
        cmd = format_curl("GET", "https://x.com",
                          headers={"Z-Header": "z", "A-Header": "a"})
        assert cmd.index("A-Header") < cmd.index("Z-Header")


# ============================================================
# mocked HTTP calls
# ============================================================

def _mock_urlopen(body: str = '{"ok":true}', status: int = 200,
                  headers: dict = None):
    """build a mock for urllib.request.urlopen."""
    resp = MagicMock()
    resp.status = status
    resp.headers = headers or {}
    resp.read.return_value = body.encode("utf-8")
    return resp


class TestGet:
    @patch("keanu.tools.httpclient.urllib.request.urlopen")
    def test_simple_get(self, mock_open):
        mock_open.return_value = _mock_urlopen()
        r = get("https://api.example.com/v1")
        assert r.status == 200
        assert r.json_body == {"ok": True}
        assert r.url == "https://api.example.com/v1"

    @patch("keanu.tools.httpclient.urllib.request.urlopen")
    def test_get_with_params(self, mock_open):
        mock_open.return_value = _mock_urlopen()
        r = get("https://x.com", params={"q": "test"})
        assert r.url == "https://x.com?q=test"


class TestPost:
    @patch("keanu.tools.httpclient.urllib.request.urlopen")
    def test_post_json(self, mock_open):
        mock_open.return_value = _mock_urlopen('{"id":1}')
        r = post("https://x.com/api", json_data={"name": "keanu"})
        assert r.status == 200
        assert r.json_body == {"id": 1}
        req = mock_open.call_args[0][0]
        assert req.get_header("Content-type") == "application/json"

    @patch("keanu.tools.httpclient.urllib.request.urlopen")
    def test_post_form(self, mock_open):
        mock_open.return_value = _mock_urlopen()
        post("https://x.com/api", data={"field": "value"})
        req = mock_open.call_args[0][0]
        assert req.get_header("Content-type") == "application/x-www-form-urlencoded"


class TestPut:
    @patch("keanu.tools.httpclient.urllib.request.urlopen")
    def test_put_json(self, mock_open):
        mock_open.return_value = _mock_urlopen('{"updated":true}')
        r = put("https://x.com/api/1", json_data={"name": "neo"})
        assert r.status == 200
        assert r.json_body == {"updated": True}


class TestDelete:
    @patch("keanu.tools.httpclient.urllib.request.urlopen")
    def test_delete(self, mock_open):
        mock_open.return_value = _mock_urlopen('', status=204)
        r = delete("https://x.com/api/1")
        assert r.status == 204


# ============================================================
# retry
# ============================================================

class TestRetry:
    @patch("keanu.tools.httpclient.time.sleep")
    def test_retries_on_failure(self, mock_sleep):
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise ConnectionError("down")
            return Response(status=200, headers={}, body="ok",
                            json_body=None, elapsed_ms=1, url="")

        cfg = RequestConfig(retries=2, retry_delay=0.1)
        r = _retry_request(flaky, cfg)
        assert r.status == 200
        assert calls["n"] == 3
        assert mock_sleep.call_count == 2

    @patch("keanu.tools.httpclient.time.sleep")
    def test_retry_exhausted_raises(self, mock_sleep):
        def always_fail():
            raise ConnectionError("down")

        cfg = RequestConfig(retries=1, retry_delay=0.01)
        try:
            _retry_request(always_fail, cfg)
            assert False, "should have raised"
        except ConnectionError:
            pass

    @patch("keanu.tools.httpclient.time.sleep")
    def test_exponential_backoff(self, mock_sleep):
        def always_fail():
            raise ConnectionError("down")

        cfg = RequestConfig(retries=3, retry_delay=1.0)
        try:
            _retry_request(always_fail, cfg)
        except ConnectionError:
            pass
        delays = [c[0][0] for c in mock_sleep.call_args_list]
        assert delays == [1.0, 2.0, 4.0]

    @patch("keanu.tools.httpclient.urllib.request.urlopen")
    def test_get_with_retries(self, mock_open):
        mock_open.return_value = _mock_urlopen()
        cfg = RequestConfig(retries=2)
        r = get("https://x.com", config=cfg)
        assert r.status == 200
