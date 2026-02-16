"""rag.py - codebase-aware retrieval augmented generation.

indexes project files into vectors for semantic search. incremental
indexing (only re-index changed files). hybrid search combining
keyword and semantic matching.

in the world: the library card catalog. instead of reading every book
to find what you need, you search the index and go straight to the shelf.
"""

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from keanu.paths import keanu_home


_RAG_DIR = keanu_home() / "rag"
_INDEX_META = _RAG_DIR / "index_meta.json"

# default patterns to skip
SKIP_PATTERNS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", "egg-info", ".eggs", ".chroma",
}

SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".so", ".dylib", ".dll",
    ".jpg", ".jpeg", ".png", ".gif", ".ico", ".svg",
    ".woff", ".woff2", ".ttf", ".eot",
    ".zip", ".tar", ".gz", ".bz2",
    ".exe", ".bin", ".dat",
}

# indexable text extensions
TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".rb",
    ".java", ".kt", ".scala", ".c", ".cpp", ".h", ".hpp",
    ".md", ".txt", ".rst", ".yaml", ".yml", ".toml", ".json",
    ".sh", ".bash", ".zsh", ".fish",
    ".html", ".css", ".scss", ".less",
    ".sql", ".graphql", ".proto",
    ".dockerfile", ".makefile",
}


@dataclass
class Chunk:
    """a chunk of text from a file, ready for indexing."""
    file_path: str
    content: str
    start_line: int
    end_line: int
    chunk_type: str = "code"  # code, docstring, comment, markdown
    hash: str = ""

    def __post_init__(self):
        if not self.hash:
            self.hash = hashlib.sha256(self.content.encode()).hexdigest()[:16]

    @property
    def id(self) -> str:
        return f"{self.file_path}:{self.start_line}-{self.end_line}:{self.hash}"


@dataclass
class SearchResult:
    """a search result from the RAG index."""
    chunk: Chunk
    score: float
    source: str = "semantic"  # semantic, keyword, hybrid


@dataclass
class IndexStats:
    """statistics about the RAG index."""
    total_files: int = 0
    total_chunks: int = 0
    indexed_at: float = 0.0
    root: str = ""


# ============================================================
# CHUNKING
# ============================================================

def chunk_file(path: str, max_chunk_lines: int = 50) -> list[Chunk]:
    """split a file into chunks for indexing.

    uses logical boundaries: functions, classes, markdown headers.
    falls back to fixed-size chunks for unstructured text.
    """
    try:
        content = Path(path).read_text(errors="replace")
    except OSError:
        return []

    lines = content.split("\n")
    ext = Path(path).suffix.lower()

    if ext == ".py":
        return _chunk_python(path, lines, max_chunk_lines)
    elif ext == ".md":
        return _chunk_markdown(path, lines, max_chunk_lines)
    else:
        return _chunk_fixed(path, lines, max_chunk_lines)


def _chunk_python(path: str, lines: list[str], max_lines: int) -> list[Chunk]:
    """chunk Python files at function/class boundaries."""
    chunks = []
    current_start = 0
    current_lines = []

    for i, line in enumerate(lines):
        # break at top-level def/class
        stripped = line.lstrip()
        is_boundary = (
            (stripped.startswith("def ") or stripped.startswith("class ")
             or stripped.startswith("async def "))
            and (not line[0].isspace() or len(line) - len(stripped) <= 4)
        )

        if is_boundary and current_lines:
            # flush current chunk
            content = "\n".join(current_lines)
            if content.strip():
                chunks.append(Chunk(
                    file_path=path,
                    content=content,
                    start_line=current_start + 1,
                    end_line=i,
                    chunk_type="code",
                ))
            current_start = i
            current_lines = [line]
        else:
            current_lines.append(line)

        # also break on max size
        if len(current_lines) >= max_lines:
            content = "\n".join(current_lines)
            if content.strip():
                chunks.append(Chunk(
                    file_path=path,
                    content=content,
                    start_line=current_start + 1,
                    end_line=i + 1,
                    chunk_type="code",
                ))
            current_start = i + 1
            current_lines = []

    # flush remainder
    if current_lines:
        content = "\n".join(current_lines)
        if content.strip():
            chunks.append(Chunk(
                file_path=path,
                content=content,
                start_line=current_start + 1,
                end_line=len(lines),
                chunk_type="code",
            ))

    return chunks


def _chunk_markdown(path: str, lines: list[str], max_lines: int) -> list[Chunk]:
    """chunk markdown files at header boundaries."""
    chunks = []
    current_start = 0
    current_lines = []

    for i, line in enumerate(lines):
        if line.startswith("#") and current_lines:
            content = "\n".join(current_lines)
            if content.strip():
                chunks.append(Chunk(
                    file_path=path,
                    content=content,
                    start_line=current_start + 1,
                    end_line=i,
                    chunk_type="markdown",
                ))
            current_start = i
            current_lines = [line]
        else:
            current_lines.append(line)

        if len(current_lines) >= max_lines:
            content = "\n".join(current_lines)
            if content.strip():
                chunks.append(Chunk(
                    file_path=path,
                    content=content,
                    start_line=current_start + 1,
                    end_line=i + 1,
                    chunk_type="markdown",
                ))
            current_start = i + 1
            current_lines = []

    if current_lines:
        content = "\n".join(current_lines)
        if content.strip():
            chunks.append(Chunk(
                file_path=path,
                content=content,
                start_line=current_start + 1,
                end_line=len(lines),
                chunk_type="markdown",
            ))

    return chunks


def _chunk_fixed(path: str, lines: list[str], max_lines: int) -> list[Chunk]:
    """fixed-size chunking for generic text files."""
    chunks = []
    for i in range(0, len(lines), max_lines):
        chunk_lines = lines[i:i + max_lines]
        content = "\n".join(chunk_lines)
        if content.strip():
            chunks.append(Chunk(
                file_path=path,
                content=content,
                start_line=i + 1,
                end_line=min(i + max_lines, len(lines)),
                chunk_type="code",
            ))
    return chunks


# ============================================================
# FILE DISCOVERY
# ============================================================

def discover_files(root: str, extensions: set[str] = None,
                   skip: set[str] = None) -> list[str]:
    """discover indexable files in a project."""
    root_path = Path(root)
    exts = extensions or TEXT_EXTENSIONS
    skip_dirs = skip or SKIP_PATTERNS

    files = []
    for path in root_path.rglob("*"):
        if not path.is_file():
            continue

        # skip directories
        parts = set(path.parts)
        if parts & skip_dirs:
            continue

        # skip by extension
        if path.suffix.lower() in SKIP_EXTENSIONS:
            continue

        # only include known text extensions (or no extension for Makefile etc)
        if path.suffix.lower() in exts or path.name.lower() in {"makefile", "dockerfile", "rakefile"}:
            files.append(str(path))

    return sorted(files)


def file_hash(path: str) -> str:
    """get a content hash for a file (for change detection)."""
    try:
        content = Path(path).read_bytes()
        return hashlib.sha256(content).hexdigest()[:16]
    except OSError:
        return ""


# ============================================================
# INDEX
# ============================================================

def build_index(root: str, max_chunk_lines: int = 50) -> IndexStats:
    """build a full RAG index for a project.

    chunks all files and stores them. returns stats.
    uses chromadb if available, falls back to JSON.
    """
    files = discover_files(root)
    all_chunks = []

    for f in files:
        chunks = chunk_file(f, max_chunk_lines)
        all_chunks.extend(chunks)

    # try chromadb first
    stored = _store_chromadb(all_chunks, root)
    if not stored:
        _store_json(all_chunks, root)

    # save metadata
    meta = {
        "root": root,
        "files": len(files),
        "chunks": len(all_chunks),
        "indexed_at": time.time(),
        "file_hashes": {f: file_hash(f) for f in files},
    }
    _save_meta(meta)

    return IndexStats(
        total_files=len(files),
        total_chunks=len(all_chunks),
        indexed_at=time.time(),
        root=root,
    )


def incremental_index(root: str, max_chunk_lines: int = 50) -> IndexStats:
    """incrementally update the index. only re-index changed files."""
    meta = _load_meta()
    old_hashes = meta.get("file_hashes", {})

    files = discover_files(root)
    changed = []
    for f in files:
        h = file_hash(f)
        if h != old_hashes.get(f, ""):
            changed.append(f)

    if not changed:
        return IndexStats(
            total_files=len(files),
            total_chunks=meta.get("chunks", 0),
            indexed_at=meta.get("indexed_at", 0),
            root=root,
        )

    # re-chunk changed files
    new_chunks = []
    for f in changed:
        chunks = chunk_file(f, max_chunk_lines)
        new_chunks.extend(chunks)

    # update store
    stored = _store_chromadb(new_chunks, root, incremental=True)
    if not stored:
        _store_json(new_chunks, root, incremental=True)

    # update metadata
    for f in changed:
        old_hashes[f] = file_hash(f)
    meta["file_hashes"] = old_hashes
    meta["indexed_at"] = time.time()
    meta["files"] = len(files)
    # approximate total chunks
    meta["chunks"] = meta.get("chunks", 0) + len(new_chunks)
    _save_meta(meta)

    return IndexStats(
        total_files=len(files),
        total_chunks=len(new_chunks),
        indexed_at=time.time(),
        root=root,
    )


# ============================================================
# SEARCH
# ============================================================

def search(query: str, root: str = "", n_results: int = 5) -> list[SearchResult]:
    """search the RAG index. tries semantic first, falls back to keyword."""
    results = _search_chromadb(query, n_results)
    if results:
        return results

    return _search_json(query, n_results)


def keyword_search(query: str, root: str = "", n_results: int = 10) -> list[SearchResult]:
    """pure keyword search across indexed chunks."""
    chunks = _load_json_chunks()
    if not chunks:
        return []

    query_words = set(query.lower().split())
    scored = []

    for chunk_data in chunks:
        content_lower = chunk_data["content"].lower()
        matches = sum(1 for w in query_words if w in content_lower)
        if matches > 0:
            score = matches / len(query_words)
            chunk = Chunk(
                file_path=chunk_data["file_path"],
                content=chunk_data["content"],
                start_line=chunk_data["start_line"],
                end_line=chunk_data["end_line"],
                chunk_type=chunk_data.get("chunk_type", "code"),
                hash=chunk_data.get("hash", ""),
            )
            scored.append(SearchResult(chunk=chunk, score=score, source="keyword"))

    scored.sort(key=lambda r: -r.score)
    return scored[:n_results]


def hybrid_search(query: str, root: str = "", n_results: int = 5) -> list[SearchResult]:
    """combine semantic and keyword search results."""
    semantic = search(query, root, n_results)
    keyword = keyword_search(query, root, n_results)

    # merge, dedup by chunk id, boost items that appear in both
    seen = {}
    for r in semantic:
        seen[r.chunk.id] = r

    for r in keyword:
        if r.chunk.id in seen:
            # boost score for items in both
            existing = seen[r.chunk.id]
            existing.score = min(1.0, existing.score + 0.2)
            existing.source = "hybrid"
        else:
            seen[r.chunk.id] = r

    results = sorted(seen.values(), key=lambda r: -r.score)
    return results[:n_results]


# ============================================================
# STORAGE BACKENDS
# ============================================================

def _store_chromadb(chunks: list[Chunk], root: str,
                    incremental: bool = False) -> bool:
    """store chunks in chromadb."""
    try:
        import chromadb
    except ImportError:
        return False

    chroma_dir = str(_RAG_DIR / "chroma")

    try:
        client = chromadb.PersistentClient(path=chroma_dir)

        if not incremental:
            try:
                client.delete_collection("keanu_rag")
            except Exception:
                pass

        collection = client.get_or_create_collection(
            name="keanu_rag",
            metadata={"hnsw:space": "cosine"},
        )

        if not chunks:
            return True

        # batch upsert
        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            collection.upsert(
                ids=[c.id for c in batch],
                documents=[c.content for c in batch],
                metadatas=[{
                    "file_path": c.file_path,
                    "start_line": c.start_line,
                    "end_line": c.end_line,
                    "chunk_type": c.chunk_type,
                } for c in batch],
            )

        return True
    except Exception:
        return False


def _search_chromadb(query: str, n_results: int) -> list[SearchResult]:
    """search chunks via chromadb."""
    try:
        import chromadb
    except ImportError:
        return []

    chroma_dir = str(_RAG_DIR / "chroma")
    if not Path(chroma_dir).exists():
        return []

    try:
        client = chromadb.PersistentClient(path=chroma_dir)
        collection = client.get_collection("keanu_rag")

        results = collection.query(
            query_texts=[query],
            n_results=n_results,
        )

        if not results["distances"] or not results["distances"][0]:
            return []

        search_results = []
        for dist, meta, doc in zip(
            results["distances"][0],
            results["metadatas"][0],
            results["documents"][0],
        ):
            chunk = Chunk(
                file_path=meta["file_path"],
                content=doc,
                start_line=meta["start_line"],
                end_line=meta["end_line"],
                chunk_type=meta.get("chunk_type", "code"),
            )
            score = 1.0 - dist  # cosine distance to similarity
            search_results.append(SearchResult(chunk=chunk, score=score, source="semantic"))

        return search_results
    except Exception:
        return []


def _store_json(chunks: list[Chunk], root: str, incremental: bool = False) -> bool:
    """fallback: store chunks as JSON."""
    json_path = _RAG_DIR / "chunks.json"
    _RAG_DIR.mkdir(parents=True, exist_ok=True)

    existing = []
    if incremental and json_path.exists():
        try:
            existing = json.loads(json_path.read_text())
        except (json.JSONDecodeError, OSError):
            existing = []

    # for incremental, remove old chunks from changed files
    if incremental and chunks:
        changed_files = {c.file_path for c in chunks}
        existing = [c for c in existing if c["file_path"] not in changed_files]

    chunk_dicts = [{
        "file_path": c.file_path,
        "content": c.content,
        "start_line": c.start_line,
        "end_line": c.end_line,
        "chunk_type": c.chunk_type,
        "hash": c.hash,
    } for c in chunks]

    all_chunks = existing + chunk_dicts
    json_path.write_text(json.dumps(all_chunks))
    return True


def _load_json_chunks() -> list[dict]:
    """load chunks from JSON fallback."""
    json_path = _RAG_DIR / "chunks.json"
    if not json_path.exists():
        return []
    try:
        return json.loads(json_path.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def _search_json(query: str, n_results: int) -> list[SearchResult]:
    """keyword-based search on JSON chunks."""
    return keyword_search(query, n_results=n_results)


# ============================================================
# METADATA
# ============================================================

def _save_meta(meta: dict):
    """save index metadata."""
    _RAG_DIR.mkdir(parents=True, exist_ok=True)
    _INDEX_META.write_text(json.dumps(meta, indent=2) + "\n")


def _load_meta() -> dict:
    """load index metadata."""
    if not _INDEX_META.exists():
        return {}
    try:
        return json.loads(_INDEX_META.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def get_index_stats() -> IndexStats:
    """get current index statistics."""
    meta = _load_meta()
    return IndexStats(
        total_files=meta.get("files", 0),
        total_chunks=meta.get("chunks", 0),
        indexed_at=meta.get("indexed_at", 0),
        root=meta.get("root", ""),
    )
