"""ingest.py - file conversion + chunking into chromadb.

takes files, converts them to text, chunks them, embeds them.
uses haystack converters as library calls (no Pipeline objects).
stores chunks in chromadb via the wellspring pattern.

in the world: the intake. everything you feed it becomes searchable.
"""

import sys
from pathlib import Path

from keanu.log import info, warn
from keanu.wellspring import depths

DEFAULT_COLLECTION = "keanu_rag"

# file types we can handle, mapped to haystack converter class names
SUPPORTED_EXTENSIONS = {
    ".pdf": "PyPDFToDocument",
    ".html": "HTMLToDocument",
    ".htm": "HTMLToDocument",
    ".md": "MarkdownToDocument",
    ".txt": "TextFileToDocument",
    ".py": "TextFileToDocument",
    ".js": "TextFileToDocument",
    ".ts": "TextFileToDocument",
    ".json": "TextFileToDocument",
    ".yaml": "TextFileToDocument",
    ".yml": "TextFileToDocument",
    ".toml": "TextFileToDocument",
    ".cfg": "TextFileToDocument",
    ".ini": "TextFileToDocument",
    ".sh": "TextFileToDocument",
    ".css": "TextFileToDocument",
    ".sql": "TextFileToDocument",
    ".rs": "TextFileToDocument",
    ".go": "TextFileToDocument",
    ".java": "TextFileToDocument",
    ".rb": "TextFileToDocument",
    ".c": "TextFileToDocument",
    ".h": "TextFileToDocument",
    ".cpp": "TextFileToDocument",
}


def _get_converter(ext):
    """get the right haystack converter for a file extension."""
    converter_name = SUPPORTED_EXTENSIONS.get(ext.lower())
    if not converter_name:
        return None

    try:
        if converter_name == "PyPDFToDocument":
            from haystack.components.converters import PyPDFToDocument
            return PyPDFToDocument()
        elif converter_name == "HTMLToDocument":
            from haystack.components.converters import HTMLToDocument
            return HTMLToDocument()
        elif converter_name == "MarkdownToDocument":
            from haystack.components.converters import MarkdownToDocument
            return MarkdownToDocument()
        elif converter_name == "TextFileToDocument":
            from haystack.components.converters import TextFileToDocument
            return TextFileToDocument()
    except ImportError as e:
        warn("ingest", f"converter not available for {ext}: {e}")
        return None


def _get_splitter():
    """get the haystack document splitter."""
    try:
        import nltk
        try:
            nltk.data.find("tokenizers/punkt_tab")
        except LookupError:
            nltk.download("punkt_tab", quiet=True)
        from haystack.components.preprocessors import DocumentSplitter
        return DocumentSplitter(
            split_by="sentence",
            split_length=5,
            split_overlap=1,
        )
    except ImportError as e:
        warn("ingest", f"missing dependency for chunking: {e}")
        return None


def _store_chunks(chunks, collection, source_path):
    """embed chunks into chromadb."""
    import chromadb

    chroma_dir = depths()
    Path(chroma_dir).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=chroma_dir)

    try:
        coll = client.get_or_create_collection(
            name=collection,
            metadata={"hnsw:space": "cosine"},
        )
    except Exception as e:
        warn("ingest", f"can't open collection {collection}: {e}")
        return 0

    ids = []
    documents = []
    metadatas = []

    for i, chunk in enumerate(chunks):
        content = chunk.content if hasattr(chunk, "content") else str(chunk)
        if not content or not content.strip():
            continue

        chunk_id = f"{source_path}:{i}"
        ids.append(chunk_id)
        documents.append(content)
        metadatas.append({
            "source": str(source_path),
            "chunk_index": i,
            "collection": collection,
        })

    if not ids:
        return 0

    coll.upsert(ids=ids, documents=documents, metadatas=metadatas)
    return len(ids)


def ingest_file(path, collection=DEFAULT_COLLECTION):
    """ingest a single file. returns {file, chunks, collection} or None on failure."""
    p = Path(path).resolve()
    if not p.exists():
        warn("ingest", f"file not found: {p}")
        return None

    ext = p.suffix
    converter = _get_converter(ext)
    if converter is None:
        warn("ingest", f"unsupported file type: {ext}")
        return None

    splitter = _get_splitter()
    if splitter is None:
        return None

    try:
        result = converter.run(sources=[p])
        docs = result.get("documents", [])
        if not docs:
            warn("ingest", f"no content extracted from {p}")
            return None

        split_result = splitter.run(documents=docs)
        chunks = split_result.get("documents", docs)

        count = _store_chunks(chunks, collection, str(p))
        info("ingest", f"ingested {p.name}: {count} chunks into {collection}")

        return {"file": str(p), "chunks": count, "collection": collection}
    except Exception as e:
        warn("ingest", f"failed to ingest {p}: {e}")
        return None


def ingest(path, collection=DEFAULT_COLLECTION):
    """ingest a file or directory. returns {files, chunks, collection}."""
    p = Path(path).resolve()

    if p.is_file():
        result = ingest_file(p, collection)
        if result:
            return {"files": 1, "chunks": result["chunks"], "collection": collection}
        return {"files": 0, "chunks": 0, "collection": collection}

    if p.is_dir():
        total_files = 0
        total_chunks = 0

        for ext in SUPPORTED_EXTENSIONS:
            for fp in p.rglob(f"*{ext}"):
                # skip hidden dirs and __pycache__
                if any(part.startswith(".") or part == "__pycache__"
                       for part in fp.parts):
                    continue

                result = ingest_file(fp, collection)
                if result:
                    total_files += 1
                    total_chunks += result["chunks"]

        info("ingest", f"batch: {total_files} files, {total_chunks} chunks into {collection}")
        return {"files": total_files, "chunks": total_chunks, "collection": collection}

    warn("ingest", f"not a file or directory: {p}")
    return {"files": 0, "chunks": 0, "collection": collection}
