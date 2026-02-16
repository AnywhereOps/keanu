"""search.py - web search + content extraction.

searches the web, fetches results, extracts text.
uses serper API when available, degrades gracefully without.

in the world: the scout that goes beyond the library walls.
"""

import os
import re

import requests

from keanu.log import info, warn, debug


def _strip_html(html):
    """minimal html to text. no deps."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _fetch_page(url, timeout=10):
    """fetch a URL, return text content."""
    try:
        resp = requests.get(url, timeout=timeout, headers={
            "User-Agent": "keanu/0.1 (research assistant)",
        })
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "html" in content_type:
            return _strip_html(resp.text)
        return resp.text[:10000]
    except Exception as e:
        debug("search", f"failed to fetch {url}: {e}")
        return None


def web_search(query, n_results=5):
    """search the web. returns list of {url, title, content, snippet}.

    uses serper.dev API if SERPER_API_KEY is set.
    returns empty list if no API key (graceful degradation).
    """
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        info("search", "no SERPER_API_KEY set, web search disabled")
        return []

    try:
        resp = requests.post(
            "https://google.serper.dev/search",
            headers={
                "X-API-KEY": api_key,
                "Content-Type": "application/json",
            },
            json={"q": query, "num": n_results},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        warn("search", f"serper API failed: {e}")
        return []

    results = []
    organic = data.get("organic", [])

    for item in organic[:n_results]:
        url = item.get("link", "")
        title = item.get("title", "")
        snippet = item.get("snippet", "")

        # fetch full page content
        content = _fetch_page(url)
        if content and len(content) > 500:
            # truncate to reasonable size for embedding
            content = content[:5000]
        elif not content:
            content = snippet

        results.append({
            "url": url,
            "title": title,
            "snippet": snippet,
            "content": content,
        })

    info("search", f"found {len(results)} results for '{query}'")
    return results
