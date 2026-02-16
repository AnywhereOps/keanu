"""forge: scaffold new abilities from the miss log.

miss -> see what's needed -> scaffold -> implement -> test -> register.
each new ability improves router coverage, revealing new gaps.
the flywheel IS convergence applied to the system itself.

in the world: the forge takes raw miss signals and hammers them into
abilities. the post-forge bake step ensures the router can find them
immediately via vectors, not just keywords.
"""

import json
import time
from pathlib import Path

from keanu.abilities.miss_tracker import analyze_misses, get_misses
from keanu.paths import keanu_home

# where abilities and tests live
ABILITIES_DIR = Path(__file__).parent
TESTS_DIR = ABILITIES_DIR.parent.parent.parent / "tests"

# registry of shared/community abilities
_REGISTRY_FILE = keanu_home() / "ability_registry.json"

ABILITY_TEMPLATE = '''\
"""{name}: {description}"""

from keanu.abilities import Ability, ability


@ability
class {class_name}Ability(Ability):

    name = "{name}"
    description = "{description}"
    keywords = [{keywords_str}]

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        p = prompt.lower()

        # exact phrase matches (high confidence)
        if any(phrase in p for phrase in self.keywords[:3]):
            return True, 0.9

        # single keyword matches
        if any(kw in p for kw in self.keywords):
            return True, 0.7

        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        # TODO: implement {name}
        return {{
            "success": True,
            "result": "{name} executed (stub)",
            "data": {{}},
        }}
'''

TEST_TEMPLATE = '''\
"""Tests for {name} ability."""

import pytest
from keanu.abilities import find_ability, _REGISTRY


class Test{class_name}Ability:

    def test_registered(self):
        assert "{name}" in _REGISTRY

    def test_can_handle_keyword(self):
        ab = _REGISTRY["{name}"]
        can, conf = ab.can_handle("{first_keyword}")
        assert can
        assert conf >= 0.7

    def test_execute_stub(self):
        ab = _REGISTRY["{name}"]
        result = ab.execute("test prompt")
        assert result["success"]
'''


def forge_ability(name: str, description: str, keywords: list[str],
                  bake: bool = False) -> dict:
    """scaffold a new ability + test from templates.

    if bake=True, re-bake the ability vectors after scaffolding
    so the router finds the new ability immediately.
    """
    # sanitize
    name = name.strip().lower().replace(" ", "_").replace("-", "_")
    class_name = "".join(w.capitalize() for w in name.split("_"))
    keywords_str = ", ".join(f'"{kw.strip()}"' for kw in keywords if kw.strip())
    first_keyword = keywords[0].strip() if keywords else name

    ability_file = ABILITIES_DIR / f"{name}.py"
    test_file = TESTS_DIR / f"test_{name}_ability.py"

    if ability_file.exists():
        return {"error": f"{ability_file} already exists"}

    ability_code = ABILITY_TEMPLATE.format(
        name=name,
        description=description,
        class_name=class_name,
        keywords_str=keywords_str,
        first_keyword=first_keyword,
    )

    test_code = TEST_TEMPLATE.format(
        name=name,
        class_name=class_name,
        first_keyword=first_keyword,
    )

    ability_file.write_text(ability_code)
    test_file.write_text(test_code)

    result = {
        "ability_file": str(ability_file),
        "test_file": str(test_file),
        "name": name,
        "class_name": class_name,
    }

    # post-forge bake: embed the new ability into vectors
    if bake:
        bake_result = bake_single_ability(name, description, keywords)
        result["baked"] = bake_result

    return result


def bake_single_ability(name: str, description: str, keywords: list[str]) -> dict:
    """bake a single ability into the vector store without full re-bake.

    incremental bake: adds documents for one ability without rebuilding
    the entire collection. much faster than full bake_abilities().
    """
    try:
        import chromadb
        from keanu.abilities.bake_abilities import CHROMA_DIR, COLLECTION_NAME

        client = chromadb.PersistentClient(path=CHROMA_DIR)
        try:
            collection = client.get_collection(COLLECTION_NAME)
        except Exception:
            # collection doesn't exist yet, create it
            collection = client.create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )

        ids = []
        documents = []
        metadatas = []

        # description doc
        ids.append(f"{name}_desc")
        documents.append(description)
        metadatas.append({"ability": name, "doc_type": "description"})

        # combined doc
        kw_str = ", ".join(keywords) if keywords else ""
        combined = f"{name}: {description}. keywords: {kw_str}" if kw_str else f"{name}: {description}"
        ids.append(f"{name}_combined")
        documents.append(combined)
        metadatas.append({"ability": name, "doc_type": "combined"})

        # keyword docs
        for i in range(0, len(keywords), 3):
            batch = keywords[i:i + 3]
            ids.append(f"{name}_kw_{i}")
            documents.append(" ".join(batch))
            metadatas.append({"ability": name, "doc_type": "keywords"})

        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        return {"success": True, "documents": len(documents)}

    except ImportError:
        return {"success": False, "error": "chromadb not available"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# ABILITY REGISTRY (sharing)
# ============================================================

def register_ability(name: str, description: str, keywords: list[str],
                     author: str = "", version: str = "0.1.0") -> dict:
    """register an ability in the local registry for sharing."""
    registry = _load_registry()

    entry = {
        "name": name,
        "description": description,
        "keywords": keywords,
        "author": author,
        "version": version,
        "registered_at": time.time(),
    }

    registry["abilities"][name] = entry
    _save_registry(registry)
    return entry


def unregister_ability(name: str) -> bool:
    """remove an ability from the registry."""
    registry = _load_registry()
    if name in registry["abilities"]:
        del registry["abilities"][name]
        _save_registry(registry)
        return True
    return False


def list_registered() -> list[dict]:
    """list all abilities in the registry."""
    registry = _load_registry()
    return list(registry["abilities"].values())


def export_ability(name: str) -> dict:
    """export an ability's source and metadata for sharing.

    returns dict with source code, test code, and metadata.
    """
    ability_file = ABILITIES_DIR / f"{name}.py"
    test_file = TESTS_DIR / f"test_{name}_ability.py"

    result = {"name": name}

    if ability_file.exists():
        result["source"] = ability_file.read_text()
        result["source_path"] = str(ability_file)
    else:
        return {"error": f"ability file not found: {ability_file}"}

    if test_file.exists():
        result["test_source"] = test_file.read_text()
        result["test_path"] = str(test_file)

    # include registry metadata if available
    registry = _load_registry()
    if name in registry["abilities"]:
        result["metadata"] = registry["abilities"][name]

    return result


def import_ability(source: str, test_source: str = "",
                   name: str = "", overwrite: bool = False) -> dict:
    """import an ability from source code.

    installs the ability file and optional test file.
    """
    if not name:
        # try to extract name from source
        for line in source.split("\n"):
            if "name = " in line and '"' in line:
                name = line.split('"')[1]
                break

    if not name:
        return {"error": "could not determine ability name"}

    ability_file = ABILITIES_DIR / f"{name}.py"
    test_file = TESTS_DIR / f"test_{name}_ability.py"

    if ability_file.exists() and not overwrite:
        return {"error": f"{ability_file} already exists (use overwrite=True)"}

    ability_file.write_text(source)
    result = {"ability_file": str(ability_file), "name": name}

    if test_source:
        test_file.write_text(test_source)
        result["test_file"] = str(test_file)

    return result


def check_ability_version(name: str) -> dict:
    """check if an ability has a newer version available in the registry."""
    registry = _load_registry()
    entry = registry["abilities"].get(name)

    if not entry:
        return {"name": name, "status": "not_registered"}

    ability_file = ABILITIES_DIR / f"{name}.py"
    if not ability_file.exists():
        return {"name": name, "status": "not_installed"}

    return {
        "name": name,
        "status": "installed",
        "version": entry.get("version", "unknown"),
        "registered_at": entry.get("registered_at", 0),
    }


# ============================================================
# REGISTRY HELPERS
# ============================================================

def _load_registry() -> dict:
    """load the ability registry."""
    if not _REGISTRY_FILE.exists():
        return {"abilities": {}, "version": 1}
    try:
        return json.loads(_REGISTRY_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {"abilities": {}, "version": 1}


def _save_registry(data: dict):
    """save the ability registry."""
    _REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    _REGISTRY_FILE.write_text(json.dumps(data, indent=2) + "\n")


def suggest_from_misses(limit: int = 50) -> list[dict]:
    """Analyze miss log and suggest potential abilities.

    Returns list of {word, count} sorted by frequency.
    """
    analysis = analyze_misses(limit)
    misses = get_misses(limit)
    total = len(misses)

    suggestions = []
    for word, count in analysis:
        suggestions.append({
            "word": word,
            "count": count,
            "pct": round(count / total * 100) if total else 0,
        })

    return suggestions
