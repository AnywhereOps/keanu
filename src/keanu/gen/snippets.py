"""snippets.py - code snippet management.

save, search, and reuse code snippets. each snippet has a name,
language, tags, and content. stored locally, searchable by keyword.

in the world: the recipe book. patterns you've used before,
ready to use again.
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from keanu.paths import keanu_home


_SNIPPETS_DIR = keanu_home() / "snippets"
_SNIPPETS_INDEX = _SNIPPETS_DIR / "index.json"


@dataclass
class Snippet:
    """a saved code snippet."""
    name: str
    content: str
    language: str = ""
    tags: list[str] = field(default_factory=list)
    description: str = ""
    created_at: float = 0.0
    used_count: int = 0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "content": self.content,
            "language": self.language,
            "tags": self.tags,
            "description": self.description,
            "created_at": self.created_at,
            "used_count": self.used_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Snippet":
        return cls(
            name=data.get("name", ""),
            content=data.get("content", ""),
            language=data.get("language", ""),
            tags=data.get("tags", []),
            description=data.get("description", ""),
            created_at=data.get("created_at", 0),
            used_count=data.get("used_count", 0),
        )


# ============================================================
# CRUD
# ============================================================

def save_snippet(snippet: Snippet) -> str:
    """save a snippet. returns the file path."""
    _SNIPPETS_DIR.mkdir(parents=True, exist_ok=True)

    path = _SNIPPETS_DIR / f"{snippet.name}.json"
    path.write_text(json.dumps(snippet.to_dict(), indent=2) + "\n")

    # update index
    _update_index(snippet)

    return str(path)


def get_snippet(name: str) -> Snippet:
    """get a snippet by name."""
    path = _SNIPPETS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"snippet not found: {name}")

    data = json.loads(path.read_text())
    return Snippet.from_dict(data)


def delete_snippet(name: str) -> bool:
    """delete a snippet."""
    path = _SNIPPETS_DIR / f"{name}.json"
    if path.exists():
        path.unlink()
        _remove_from_index(name)
        return True
    return False


def list_snippets(tag: str = "", language: str = "") -> list[dict]:
    """list all snippets, optionally filtered by tag or language."""
    index = _load_index()
    snippets = index.get("snippets", [])

    if tag:
        snippets = [s for s in snippets if tag in s.get("tags", [])]
    if language:
        snippets = [s for s in snippets if s.get("language") == language]

    return sorted(snippets, key=lambda s: -s.get("used_count", 0))


def use_snippet(name: str) -> Snippet:
    """get a snippet and increment its use count."""
    snippet = get_snippet(name)
    snippet.used_count += 1
    save_snippet(snippet)
    return snippet


# ============================================================
# SEARCH
# ============================================================

def search_snippets(query: str) -> list[Snippet]:
    """search snippets by keyword in name, description, tags, and content."""
    query_lower = query.lower()
    results = []

    if not _SNIPPETS_DIR.is_dir():
        return []

    for path in _SNIPPETS_DIR.glob("*.json"):
        if path.name == "index.json":
            continue
        try:
            data = json.loads(path.read_text())
            snippet = Snippet.from_dict(data)

            # score based on matches
            score = 0
            if query_lower in snippet.name.lower():
                score += 3
            if query_lower in snippet.description.lower():
                score += 2
            if any(query_lower in t.lower() for t in snippet.tags):
                score += 2
            if query_lower in snippet.content.lower():
                score += 1

            if score > 0:
                results.append((score, snippet))
        except (json.JSONDecodeError, OSError):
            pass

    results.sort(key=lambda x: -x[0])
    return [s for _, s in results]


# ============================================================
# INDEX
# ============================================================

def _load_index() -> dict:
    """load the snippets index."""
    if not _SNIPPETS_INDEX.exists():
        return {"snippets": []}
    try:
        return json.loads(_SNIPPETS_INDEX.read_text())
    except (json.JSONDecodeError, OSError):
        return {"snippets": []}


def _save_index(index: dict):
    """save the snippets index."""
    _SNIPPETS_DIR.mkdir(parents=True, exist_ok=True)
    _SNIPPETS_INDEX.write_text(json.dumps(index, indent=2) + "\n")


def _update_index(snippet: Snippet):
    """update the index with a snippet's metadata."""
    index = _load_index()
    snippets = index.get("snippets", [])

    # remove existing entry
    snippets = [s for s in snippets if s.get("name") != snippet.name]

    # add updated entry
    snippets.append({
        "name": snippet.name,
        "language": snippet.language,
        "tags": snippet.tags,
        "description": snippet.description,
        "used_count": snippet.used_count,
    })

    index["snippets"] = snippets
    _save_index(index)


def _remove_from_index(name: str):
    """remove a snippet from the index."""
    index = _load_index()
    index["snippets"] = [s for s in index.get("snippets", []) if s.get("name") != name]
    _save_index(index)


def rebuild_index() -> int:
    """rebuild the index from snippet files."""
    if not _SNIPPETS_DIR.is_dir():
        return 0

    snippets = []
    for path in _SNIPPETS_DIR.glob("*.json"):
        if path.name == "index.json":
            continue
        try:
            data = json.loads(path.read_text())
            snippets.append({
                "name": data.get("name", path.stem),
                "language": data.get("language", ""),
                "tags": data.get("tags", []),
                "description": data.get("description", ""),
                "used_count": data.get("used_count", 0),
            })
        except (json.JSONDecodeError, OSError):
            pass

    _save_index({"snippets": snippets})
    return len(snippets)
