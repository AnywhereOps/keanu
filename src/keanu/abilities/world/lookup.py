"""lookup.py - web lookup ability.

fetch docs, search the web, read API references. cache per session.
when craft hits an unfamiliar library or error, look it up instead of guessing.

in the world: the library card. you don't memorize every book.
you know how to find the one you need.
"""

import re
import time
import hashlib
from urllib.parse import urlparse

import requests

from keanu.abilities import Ability, ability


# session-level cache. cleared when the process dies.
_CACHE: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 600  # 10 minutes


def _cache_key(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def _get_cached(url: str) -> str | None:
    key = _cache_key(url)
    if key in _CACHE:
        content, ts = _CACHE[key]
        if time.time() - ts < _CACHE_TTL:
            return content
        del _CACHE[key]
    return None


def _set_cached(url: str, content: str):
    key = _cache_key(url)
    _CACHE[key] = (content, time.time())


def fetch_url(url: str, max_chars: int = 20000) -> dict:
    """fetch a URL and return cleaned text content.

    strips HTML tags, scripts, styles. returns plain text.
    respects a character limit to avoid blowing up context.
    """
    cached = _get_cached(url)
    if cached:
        return {"success": True, "content": cached[:max_chars], "cached": True}

    try:
        resp = requests.get(
            url,
            timeout=15,
            headers={"User-Agent": "keanu/1.0 (coding assistant)"},
            allow_redirects=True,
        )
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        return {"success": False, "content": f"timeout fetching {url}"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "content": f"cannot connect to {url}"}
    except requests.exceptions.HTTPError as e:
        return {"success": False, "content": f"HTTP {e.response.status_code}: {url}"}
    except Exception as e:
        return {"success": False, "content": f"fetch error: {e}"}

    content_type = resp.headers.get("content-type", "")
    text = resp.text

    # strip HTML if needed
    if "html" in content_type or text.strip().startswith("<"):
        text = _html_to_text(text)

    text = text[:max_chars]
    _set_cached(url, text)
    return {"success": True, "content": text, "cached": False}


def _html_to_text(html: str) -> str:
    """strip HTML to plain text. no external deps."""
    # remove script/style blocks
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # remove nav, header, footer for cleaner content
    text = re.sub(r'<(nav|header|footer)[^>]*>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # convert common block elements to newlines
    text = re.sub(r'<(br|hr|/p|/div|/h[1-6]|/li|/tr)[^>]*>', '\n', text, flags=re.IGNORECASE)
    # strip remaining tags
    text = re.sub(r'<[^>]+>', '', text)
    # decode common entities
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"').replace('&#39;', "'").replace('&nbsp;', ' ')
    # collapse whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


def search_docs(query: str, site: str = "") -> dict:
    """search for documentation. uses DuckDuckGo HTML API.

    site param restricts to a domain (e.g. "docs.python.org").
    returns top results as a list of {title, url, snippet}.
    """
    search_query = f"{query} site:{site}" if site else query

    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": search_query},
            timeout=10,
            headers={"User-Agent": "keanu/1.0 (coding assistant)"},
        )
        resp.raise_for_status()
    except Exception as e:
        return {"success": False, "results": [], "error": str(e)}

    results = _parse_ddg_results(resp.text)
    return {"success": True, "results": results[:5]}


def _parse_ddg_results(html: str) -> list[dict]:
    """parse DuckDuckGo HTML results into structured data."""
    results = []
    # DuckDuckGo HTML wraps results in <a class="result__a">
    links = re.findall(
        r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
        html, re.DOTALL
    )
    snippets = re.findall(
        r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
        html, re.DOTALL
    )

    for i, (url, title) in enumerate(links):
        title_clean = re.sub(r'<[^>]+>', '', title).strip()
        snippet = ""
        if i < len(snippets):
            snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip()

        # skip ads and internal ddg links
        if "duckduckgo.com" in url:
            continue

        results.append({
            "title": title_clean[:120],
            "url": url,
            "snippet": snippet[:200],
        })

    return results


# doc site shortcuts for common libraries
_DOC_SITES = {
    "python": "docs.python.org",
    "django": "docs.djangoproject.com",
    "flask": "flask.palletsprojects.com",
    "fastapi": "fastapi.tiangolo.com",
    "requests": "docs.python-requests.org",
    "numpy": "numpy.org/doc",
    "pandas": "pandas.pydata.org/docs",
    "pytest": "docs.pytest.org",
    "react": "react.dev",
    "node": "nodejs.org/docs",
    "go": "pkg.go.dev",
    "rust": "doc.rust-lang.org",
    "mdn": "developer.mozilla.org",
}


@ability
class LookupAbility(Ability):

    name = "lookup"
    description = "Search docs, fetch URLs, read API references"
    keywords = ["lookup", "docs", "documentation", "search web", "fetch url", "api reference"]
    cast_line = "lookup consults the scrolls..."

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        p = prompt.lower()
        if any(kw in p for kw in ["look up", "fetch", "docs for", "documentation"]):
            return True, 0.7
        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        ctx = context or {}

        url = ctx.get("url", "")
        query = ctx.get("query", "")
        site = ctx.get("site", "")
        library = ctx.get("library", "")

        # resolve library shortcut to site
        if library and not site:
            site = _DOC_SITES.get(library.lower(), "")

        # mode 1: fetch a specific URL
        if url:
            result = fetch_url(url)
            if result["success"]:
                return {
                    "success": True,
                    "result": result["content"],
                    "data": {"url": url, "cached": result.get("cached", False)},
                }
            return {"success": False, "result": result["content"], "data": {}}

        # mode 2: search for docs
        if query:
            result = search_docs(query, site=site)
            if not result["success"]:
                return {"success": False, "result": f"Search failed: {result.get('error', 'unknown')}", "data": {}}

            if not result["results"]:
                return {"success": True, "result": "No results found.", "data": {"results": []}}

            # format results
            lines = []
            for r in result["results"]:
                lines.append(f"- {r['title']}")
                lines.append(f"  {r['url']}")
                if r["snippet"]:
                    lines.append(f"  {r['snippet']}")
                lines.append("")

            return {
                "success": True,
                "result": "\n".join(lines),
                "data": {"results": result["results"]},
            }

        # mode 3: use prompt as query
        if prompt:
            result = search_docs(prompt, site=site)
            if result["success"] and result["results"]:
                lines = []
                for r in result["results"]:
                    lines.append(f"- {r['title']}: {r['url']}")
                return {
                    "success": True,
                    "result": "\n".join(lines),
                    "data": {"results": result["results"]},
                }

        return {"success": False, "result": "Provide a url or query.", "data": {}}
