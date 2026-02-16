"""bake_abilities.py - embed ability descriptions into chromadb for vector routing.

each ability gets multiple documents: the description, each keyword,
and a combined summary. query the collection to find the best ability
for any prompt. falls back to keyword matching when not baked.

in the world: the grimoire gets a map. you don't need to know the spell's
exact name anymore. describe what you want, and the right page opens.
"""

from pathlib import Path

CHROMA_DIR = str(Path(__file__).resolve().parent.parent.parent.parent / ".chroma")
COLLECTION_NAME = "keanu_abilities"


def bake_abilities():
    """embed all registered ability metadata into chromadb."""
    import chromadb
    from keanu.abilities import list_abilities

    abilities = list_abilities()
    if not abilities:
        print("  no abilities registered. skipping.")
        return

    print(f"\n  baking {len(abilities)} abilities into vector store...")

    client = chromadb.PersistentClient(path=CHROMA_DIR)

    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    ids = []
    documents = []
    metadatas = []

    for ab in abilities:
        name = ab["name"]
        desc = ab["description"]
        keywords = ab.get("keywords", [])

        # doc 1: the description
        ids.append(f"{name}_desc")
        documents.append(desc)
        metadatas.append({"ability": name, "doc_type": "description"})

        # doc 2: combined summary
        kw_str = ", ".join(keywords) if keywords else ""
        combined = f"{name}: {desc}. keywords: {kw_str}" if kw_str else f"{name}: {desc}"
        ids.append(f"{name}_combined")
        documents.append(combined)
        metadatas.append({"ability": name, "doc_type": "combined"})

        # doc 3+: each keyword (grouped in small batches to avoid too many tiny docs)
        if keywords:
            # batch keywords into groups of 3-4 for better embedding quality
            for i in range(0, len(keywords), 3):
                batch = keywords[i:i + 3]
                ids.append(f"{name}_kw_{i}")
                documents.append(" ".join(batch))
                metadatas.append({"ability": name, "doc_type": "keywords"})

    print(f"  embedding {len(documents)} ability documents...")
    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    print(f"  abilities baked: {', '.join(ab['name'] for ab in abilities)}")


def query_abilities(prompt, n_results=3):
    """query the baked abilities collection. returns list of (ability_name, distance)."""
    import chromadb

    chroma_dir = Path(CHROMA_DIR)
    if not chroma_dir.exists():
        return []

    try:
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        collection = client.get_collection(COLLECTION_NAME)
    except Exception:
        return []

    results = collection.query(
        query_texts=[prompt],
        n_results=n_results,
    )

    if not results["distances"] or not results["distances"][0]:
        return []

    # deduplicate by ability name, keep best (lowest distance) per ability
    seen = {}
    for dist, meta in zip(results["distances"][0], results["metadatas"][0]):
        name = meta["ability"]
        if name not in seen or dist < seen[name]:
            seen[name] = dist

    # return sorted by distance (best first)
    return sorted(seen.items(), key=lambda x: x[1])


def has_baked_abilities():
    """check if the abilities collection exists."""
    chroma_dir = Path(CHROMA_DIR)
    if not chroma_dir.exists():
        return False
    try:
        import chromadb
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        client.get_collection(COLLECTION_NAME)
        return True
    except Exception:
        return False
