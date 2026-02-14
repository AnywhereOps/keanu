"""bridge.py - openpaw integration. hybrid search, similarity dedup, store.

uses openclaw CLI as the bridge. keanu stays Python, openpaw stays TypeScript.
the bridge is a subprocess call. simple. works now.
"""

import json
import subprocess

from keanu.log import info, warn, debug


_openpaw_checked = None


def openpaw_available(*, _reset: bool = False) -> bool:
    """Check if openclaw CLI is available. Cached after first check."""
    global _openpaw_checked
    if _reset:
        _openpaw_checked = None
    if _openpaw_checked is not None:
        return _openpaw_checked
    try:
        result = subprocess.run(
            ["openclaw", "--version"],
            capture_output=True, text=True, timeout=5,
        )
        _openpaw_checked = result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        _openpaw_checked = False
    if _openpaw_checked:
        debug("bridge", "openclaw available")
    return _openpaw_checked


def recall_via_openpaw(query: str, max_results: int = 6,
                       min_score: float = 0.35) -> list:
    """Hybrid vector+BM25 search via openclaw memory search."""
    cmd = [
        "openclaw", "memory", "search", query,
        "--json",
        "--max-results", str(max_results),
        "--min-score", str(min_score),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return []
        data = json.loads(result.stdout)
        results = data.get("results", [])
        debug("bridge", f"recall: {len(results)} results for '{query[:40]}'")
        return results
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return []


def store_via_openpaw(content: str, memory_type: str = "",
                      tags: list = None) -> bool:
    """Store a memory in openpaw's vector store for hybrid search."""
    if not openpaw_available():
        return False
    formatted = f"[{memory_type}] {content}" if memory_type else content
    if tags:
        formatted += f"\ntags: {', '.join(tags)}"
    cmd = ["openclaw", "memory", "store", formatted]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            debug("bridge", f"stored: {content[:40]}")
            return True
        return False
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def similarity_check(content: str, threshold: float = 0.95) -> dict | None:
    """Check if similar content already exists in openpaw. Returns match or None.

    Uses vector similarity (cosine distance). Catches paraphrases that
    exact SHA256 hash would miss. Like openpaw's memory-lancedb dedup.
    """
    if not openpaw_available():
        return None
    results = recall_via_openpaw(content, max_results=1, min_score=threshold)
    if results:
        debug("bridge", f"similar content found (score={results[0].get('score', '?')})")
        return results[0]
    return None


# ============================================================
# AUTO-CAPTURE: extract memorable content from conversations
# ============================================================

# Keyword triggers (from openpaw's shouldCapture pattern)
CAPTURE_TRIGGERS = [
    "remember", "don't forget", "important:", "note to self",
    "always ", "never ", "prefer", "decision:", "lesson:",
    "i want", "i need", "my goal", "the plan is",
]

# Category detection (from openpaw's detectCategory pattern)
CATEGORY_RULES = [
    ("preference", ["prefer", "like", "hate", "want", "need", "love", "rather"]),
    ("decision", ["decided", "will use", "going with", "chose", "picking"]),
    ("goal", ["goal", "plan to", "want to", "going to build", "shipping"]),
    ("lesson", ["learned", "lesson", "mistake", "never again", "turns out"]),
    ("commitment", ["promise", "commit", "deadline", "by friday", "by monday"]),
    ("fact", ["is", "are", "has", "have", "lives in", "works at"]),
]


def detect_category(text: str) -> str:
    """Auto-detect memory type from content. Returns MemoryType value."""
    lower = text.lower()
    for category, keywords in CATEGORY_RULES:
        if any(kw in lower for kw in keywords):
            return category
    return "fact"


def should_capture(text: str) -> bool:
    """Check if text contains a capture trigger."""
    lower = text.lower()
    return any(trigger in lower for trigger in CAPTURE_TRIGGERS)


def capture_from_conversation(messages: list[str]) -> list[dict]:
    """Extract memorable content from a list of messages.

    Returns list of {content, memory_type, importance} dicts ready
    for store.remember().
    """
    captures = []
    for msg in messages:
        if not should_capture(msg):
            continue
        category = detect_category(msg)
        # skip if already stored (similarity check)
        if similarity_check(msg, threshold=0.90):
            continue
        captures.append({
            "content": msg.strip(),
            "memory_type": category,
            "importance": 7 if category in ("goal", "commitment", "decision") else 5,
        })
        if len(captures) >= 5:  # cap per conversation
            break
    info("bridge", f"captured {len(captures)} memories from conversation")
    return captures


# ============================================================
# AUTO-RECALL: inject relevant memories into context
# ============================================================

def context_inject(prompt: str, limit: int = 3) -> str:
    """Search memories and format as context block for injection.

    Returns formatted string to prepend to system prompt, or empty string.
    Like openpaw's before_agent_start memory injection.
    """
    if not openpaw_available():
        return ""
    results = recall_via_openpaw(prompt, max_results=limit, min_score=0.3)
    if not results:
        return ""
    lines = ["<relevant-memories>"]
    for r in results:
        snippet = r.get("snippet", "").strip()
        score = r.get("score", 0)
        if snippet:
            lines.append(f"- [{score:.2f}] {snippet[:200]}")
    lines.append("</relevant-memories>")
    info("bridge", f"injecting {len(results)} memories into context")
    return "\n".join(lines)
