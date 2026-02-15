"""wellspring.py - the deep pool. all vector memory flows through here.

The system uses vector embeddings (chromadb) to match text against
trained patterns. Detect uses them to spot cognitive patterns like
sycophancy. Scan uses them to read the three-primary color model.
Both used to have their own copy of the same setup code. Now there's
one wellspring. Everyone draws from it.

in the world: detect and scan used to have their own eyes.
now there's one pool they both look into.
"""

import re
import sys
from pathlib import Path


def depths():
    """Returns the file path to the .chroma directory where all vector
    databases are stored. This is relative to the project root (three
    directories up from this file).

    in the world: where the vectors sleep.
    """
    return str(Path(__file__).resolve().parent.parent.parent / ".chroma")


def tap(collection):
    """Opens a BehavioralStore and checks if it has the named collection.
    BehavioralStore is keanu's own transparent vector format (no chromadb
    dependency). Returns the store if the collection exists, None otherwise.
    Fails silently if BehavioralStore isn't installed.

    Collections: "silverado" for detect patterns, "silverado_rgb" for scan.

    in the world: tap into a specific vein of the wellspring.
    """
    try:
        from keanu.compress.behavioral import BehavioralStore
        store = BehavioralStore()
        if store.has_collection(collection):
            return store
    except ImportError:
        pass
    return None


def draw(collection):
    """Opens a chromadb collection by name. Handles all the setup:
    importing chromadb, finding the .chroma directory, creating the
    persistent client, and looking up the collection. Returns the
    collection object if everything works, None if anything fails
    (missing chromadb, no vectors baked, collection not found).
    Prints helpful error messages to stderr.

    Collections: "silverado" for detect patterns, "silverado_rgb" for scan.

    in the world: draw water from the deep pool.
    """
    try:
        import chromadb
    except ImportError:
        print("  pip install chromadb", file=sys.stderr)
        return None

    chroma_dir = depths()
    if not Path(chroma_dir).exists():
        print("  no vectors found. run: keanu bake", file=sys.stderr)
        return None

    client = chromadb.PersistentClient(path=chroma_dir)

    try:
        return client.get_collection(collection)
    except Exception:
        print(f"  collection '{collection}' not found. run: keanu bake", file=sys.stderr)
        return None


def sift(lines):
    """Takes a list of text lines and returns only the ones worth scanning.
    Skips lines that are too short (under 20 chars), code (imports, defs,
    classes), markdown formatting (headers, fences, tables), and regex
    patterns. Returns a list of (line_number, text) tuples where
    line_number is 1-indexed.

    Both detect and scan need this same filter. Written once here.

    in the world: sift the sand, keep the gold.
    """
    scannable = []
    for i, line in enumerate(lines):
        s = line.strip()
        if (len(s) < 20
                or s.startswith(("#", "```", "import ", "from ", "def ", "class "))
                or re.match(r'^[\s\-\|=\+\*`#>]+$', s)
                or re.match(r'^r["\']', s)):
            continue
        scannable.append((i + 1, s))
    return scannable
