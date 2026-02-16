"""httpclient.py - lightweight HTTP client. urllib under the hood.

wraps urllib so keanu can make API calls, web lookups, and external
service calls without pulling in requests. one module, pure stdlib.

Response and RequestConfig are dataclasses. get/post/put/delete are
the public API. _request does the actual work. retry logic uses
exponential backoff. format_curl generates debug commands.

in the world: the messenger. carries fire to the outside and brings
answers back. no third-party courier required.
"""

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# ============================================================
# DATA
# ============================================================

@dataclass
class Response:
    """an HTTP response. status, headers, body, timing."""
    status: int
    headers: dict
    body: str
    json_body: Optional[dict]
    elapsed_ms: float
    url: str


@dataclass
class RequestConfig:
    """knobs for a request. timeout, retries, redirects, ssl."""
    timeout: int = 30
    retries: int = 0
    retry_delay: float = 1.0
    headers: dict = field(default_factory=dict)
    follow_redirects: bool = True
    verify_ssl: bool = True


# ============================================================
# URL HELPERS
# ============================================================

def build_url(base: str, path: str = "", params: dict = None) -> str:
    """assemble a URL from base, path, and query params."""
    url = base.rstrip("/")
    if path:
        url = url + "/" + path.lstrip("/")
    if params:
        qs = urllib.parse.urlencode(params, doseq=True)
        sep = "&" if "?" in url else "?"
        url = url + sep + qs
    return url


# ============================================================
# RESPONSE HELPERS
# ============================================================

def parse_json_response(response: Response) -> dict:
    """parse body as JSON. raises ValueError on failure."""
    try:
        return json.loads(response.body)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"failed to parse JSON from {response.url}: {exc}")


def is_success(response: Response) -> bool:
    """true if 2xx."""
    return 200 <= response.status < 300


def is_redirect(response: Response) -> bool:
    """true if 3xx."""
    return 300 <= response.status < 400


def is_error(response: Response) -> bool:
    """true if 4xx or 5xx."""
    return response.status >= 400


# ============================================================
# DEBUG
# ============================================================

def format_curl(method: str, url: str, headers: dict = None,
                data: dict = None) -> str:
    """generate an equivalent curl command for debugging."""
    parts = ["curl", "-X", method]
    if headers:
        for k, v in sorted(headers.items()):
            parts.append(f"-H '{k}: {v}'")
    if data:
        parts.append(f"-d '{json.dumps(data)}'")
    parts.append(f"'{url}'")
    return " ".join(parts)


# ============================================================
# RETRY
# ============================================================

def _retry_request(fn: Callable[[], Response],
                   config: RequestConfig) -> Response:
    """call fn up to 1 + config.retries times with exponential backoff."""
    last_exc = None
    delay = config.retry_delay
    for attempt in range(1 + config.retries):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt < config.retries:
                time.sleep(delay)
                delay *= 2
    raise last_exc  # type: ignore[misc]


# ============================================================
# CORE
# ============================================================

def _request(method: str, url: str, data: Optional[bytes] = None,
             headers: dict = None, config: RequestConfig = None) -> Response:
    """send an HTTP request via urllib. returns a Response."""
    config = config or RequestConfig()

    merged_headers = dict(config.headers)
    if headers:
        merged_headers.update(headers)

    req = urllib.request.Request(url, data=data, headers=merged_headers,
                                method=method.upper())

    ctx = None
    if not config.verify_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    def do_request() -> Response:
        t0 = time.monotonic()
        try:
            resp = urllib.request.urlopen(
                req, timeout=config.timeout, context=ctx
            )
            status = resp.status
            resp_headers = dict(resp.headers)
            body = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            status = exc.code
            resp_headers = dict(exc.headers) if exc.headers else {}
            body = exc.read().decode("utf-8", errors="replace")
        elapsed = (time.monotonic() - t0) * 1000

        json_body = None
        try:
            json_body = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            pass

        return Response(
            status=status,
            headers=resp_headers,
            body=body,
            json_body=json_body,
            elapsed_ms=round(elapsed, 2),
            url=url,
        )

    if config.retries > 0:
        return _retry_request(do_request, config)
    return do_request()


# ============================================================
# PUBLIC API
# ============================================================

def get(url: str, params: dict = None, headers: dict = None,
        config: RequestConfig = None) -> Response:
    """HTTP GET."""
    if params:
        url = build_url(url, params=params)
    return _request("GET", url, headers=headers, config=config)


def post(url: str, data: dict = None, json_data: dict = None,
         headers: dict = None, config: RequestConfig = None) -> Response:
    """HTTP POST. pass data for form-encoded, json_data for JSON body."""
    body_bytes, extra_headers = _encode_body(data, json_data)
    merged = dict(extra_headers)
    if headers:
        merged.update(headers)
    return _request("POST", url, data=body_bytes, headers=merged,
                    config=config)


def put(url: str, data: dict = None, json_data: dict = None,
        headers: dict = None, config: RequestConfig = None) -> Response:
    """HTTP PUT. pass data for form-encoded, json_data for JSON body."""
    body_bytes, extra_headers = _encode_body(data, json_data)
    merged = dict(extra_headers)
    if headers:
        merged.update(headers)
    return _request("PUT", url, data=body_bytes, headers=merged,
                    config=config)


def delete(url: str, headers: dict = None,
           config: RequestConfig = None) -> Response:
    """HTTP DELETE."""
    return _request("DELETE", url, headers=headers, config=config)


def _encode_body(data: dict = None,
                 json_data: dict = None) -> tuple[Optional[bytes], dict]:
    """encode a request body. returns (bytes, extra_headers)."""
    if json_data is not None:
        return (json.dumps(json_data).encode("utf-8"),
                {"Content-Type": "application/json"})
    if data is not None:
        return (urllib.parse.urlencode(data).encode("utf-8"),
                {"Content-Type": "application/x-www-form-urlencoded"})
    return None, {}
