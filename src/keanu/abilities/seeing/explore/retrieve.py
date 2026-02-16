"""retrieve.py - query vectors, rank results, build context.

the core retrieval layer. queries chromadb, formats results
as context the oracle can consume.

in the world: the librarian. ask a question, get the right pages.
"""

from keanu.log import info, debug
from keanu.wellspring import draw

DEFAULT_COLLECTION = "keanu_rag"


def retrieve(query, n_results=5, collection=DEFAULT_COLLECTION):
    """query the vector store. returns list of {content, source, chunk_index, distance}."""
    coll = draw(collection)
    if coll is None:
        return []

    try:
        results = coll.query(
            query_texts=[query],
            n_results=n_results,
        )
    except Exception as e:
        debug("retrieve", f"query failed: {e}")
        return []

    if not results["documents"] or not results["documents"][0]:
        return []

    chunks = []
    docs = results["documents"][0]
    distances = results["distances"][0] if results.get("distances") else [0.0] * len(docs)
    metadatas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)

    for doc, dist, meta in zip(docs, distances, metadatas):
        chunks.append({
            "content": doc,
            "source": meta.get("source", "unknown"),
            "chunk_index": meta.get("chunk_index", 0),
            "distance": dist,
        })

    info("retrieve", f"found {len(chunks)} chunks for '{query[:50]}'")
    return chunks


def build_context(query, n_results=5, collection=DEFAULT_COLLECTION,
                  include_web=False):
    """retrieve relevant chunks and format as a context block for the oracle.

    returns a string that can be prepended to an oracle prompt.
    returns empty string if nothing relevant found.
    """
    chunks = retrieve(query, n_results, collection)

    # optionally add web results
    if include_web:
        from keanu.abilities.seeing.explore.search import web_search
        web_results = web_search(query, n_results=3)
        for r in web_results:
            chunks.append({
                "content": r["content"],
                "source": r["url"],
                "chunk_index": 0,
                "distance": 0.5,  # neutral distance for web results
            })

    if not chunks:
        return ""

    lines = ["[CONTEXT: Retrieved from ingested documents]", ""]
    for i, chunk in enumerate(chunks):
        source = chunk["source"]
        content = chunk["content"].strip()
        if not content:
            continue
        lines.append(f"--- Source: {source} ---")
        lines.append(content)
        lines.append("")

    lines.append("[END CONTEXT]")
    lines.append("")

    context = "\n".join(lines)
    info("retrieve", f"built context: {len(chunks)} chunks, {len(context)} chars")
    return context
