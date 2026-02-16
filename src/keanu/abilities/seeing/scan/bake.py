"""
bake.py - turns examples into vectors.

parses lens-examples-rgb.md, embeds into chromadb, calibrates balance.
run once after editing examples. after that, everything is pure math.
"""

import sys
import re
import argparse
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CHROMA_DIR = str(PACKAGE_ROOT / ".chroma")
DEFAULT_EXAMPLES = str(PACKAGE_ROOT / "examples" / "reference-examples.md")
DEFAULT_LENSES = str(PACKAGE_ROOT / "examples" / "lens-examples-rgb.md")

PRIMARIES = ("red", "yellow", "blue")


def parse_reference_file(filepath):
    with open(filepath) as f:
        content = f.read()

    examples = []
    current_detector = None
    current_valence = None

    for line in content.split('\n'):
        det_match = re.match(r'^## (?:\w+/)?(\w+)\.py', line.strip())
        if det_match:
            raw = det_match.group(1)
            current_detector = raw.replace('_detector', '').replace('_monitor', '').replace('_audit', '').replace('_check', '')
            current_valence = None
            continue

        if line.strip().startswith('### POSITIVE'):
            current_valence = 'positive'
            continue
        if line.strip().startswith('### NEGATIVE'):
            current_valence = 'negative'
            continue

        if line.strip() == '```' or line.strip() == '---' or line.strip().startswith('#'):
            continue

        text = line.strip()
        if text and current_detector and current_valence and len(text) > 10:
            examples.append({
                'detector': current_detector,
                'valence': current_valence,
                'text': text,
            })

    return examples


def parse_lens_file(filepath):
    with open(filepath) as f:
        content = f.read()

    examples = []
    current_lens = None
    current_valence = None

    for line in content.split('\n'):
        lens_match = re.match(r'^## (\w+)', line.strip())
        if lens_match:
            current_lens = lens_match.group(1)
            current_valence = None
            continue

        if line.strip().startswith('### POSITIVE'):
            current_valence = 'positive'
            continue
        if line.strip().startswith('### NEGATIVE'):
            current_valence = 'negative'
            continue

        if line.strip() == '```' or line.strip() == '---' or line.strip().startswith('#'):
            continue

        text = line.strip()
        if text and current_lens and current_valence and len(text) > 10:
            examples.append({
                'lens': current_lens,
                'valence': current_valence,
                'text': text,
            })

    return examples


def bake_detectors(examples_path=None):
    import chromadb

    if examples_path is None:
        examples_path = DEFAULT_EXAMPLES

    if not Path(examples_path).exists():
        print(f"  {examples_path} not found. skipping detectors.")
        return

    print(f"  parsing {examples_path}...")
    examples = parse_reference_file(examples_path)

    detectors = set(e['detector'] for e in examples)
    print(f"  found {len(examples)} examples across {len(detectors)} detectors:")
    for d in sorted(detectors):
        pos = sum(1 for e in examples if e['detector'] == d and e['valence'] == 'positive')
        neg = sum(1 for e in examples if e['detector'] == d and e['valence'] == 'negative')
        print(f"    {d}: {pos} positive, {neg} negative")

    print(f"\n  opening chromadb at {CHROMA_DIR}...")
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    try:
        client.delete_collection("silverado")
    except Exception:
        pass

    collection = client.create_collection(
        name="silverado",
        metadata={"hnsw:space": "cosine"},
    )

    ids = []
    documents = []
    metadatas = []

    for i, ex in enumerate(examples):
        ids.append(f"{ex['detector']}_{ex['valence']}_{i}")
        documents.append(ex['text'])
        metadatas.append({
            'detector': ex['detector'],
            'valence': ex['valence'],
            'source': 'silverado-bootstrap-v1',
        })

    print(f"  embedding {len(documents)} detector examples...")
    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    print(f"  detectors baked: {', '.join(sorted(detectors))}")


def bake_helix(lenses_path=None):
    import chromadb

    if lenses_path is None:
        lenses_path = DEFAULT_LENSES

    if not Path(lenses_path).exists():
        print(f"  {lenses_path} not found. skipping helix.")
        return

    print(f"\n  parsing {lenses_path}...")
    examples = parse_lens_file(lenses_path)

    lenses = set(e['lens'] for e in examples)
    print(f"  found {len(examples)} examples across {len(lenses)} lenses:")
    for lens in sorted(lenses):
        pos = sum(1 for e in examples if e['lens'] == lens and e['valence'] == 'positive')
        neg = sum(1 for e in examples if e['lens'] == lens and e['valence'] == 'negative')
        print(f"    {lens}: {pos} positive, {neg} negative")

    client = chromadb.PersistentClient(path=CHROMA_DIR)

    try:
        client.delete_collection("silverado_rgb")
    except Exception:
        pass

    collection = client.create_collection(
        name="silverado_rgb",
        metadata={"hnsw:space": "cosine"},
    )

    ids = []
    documents = []
    metadatas = []

    for i, ex in enumerate(examples):
        ids.append(f"{ex['lens']}_{ex['valence']}_{i}")
        documents.append(ex['text'])
        metadatas.append({
            'lens': ex['lens'],
            'valence': ex['valence'],
            'source': 'silverado-rgb-v1',
        })

    print(f"  embedding {len(documents)} lens examples...")
    collection.add(ids=ids, documents=documents, metadatas=metadatas)

    # calibration: balance the three primaries
    print(f"\n  calibrating lens balance...")

    corrections = {p: 1.0 for p in PRIMARIES}
    max_iterations = 10
    tolerance = 0.02
    stall_threshold = 0.005

    last_diff = None
    stall_count = 0
    diff = 1.0

    for iteration in range(max_iterations):
        cluster_avgs = {}

        for lens_name in PRIMARIES:
            pos_examples = [e['text'] for e in examples if e['lens'] == lens_name and e['valence'] == 'positive']
            neg_examples = [e['text'] for e in examples if e['lens'] == lens_name and e['valence'] == 'negative']
            if len(pos_examples) < 2:
                cluster_avgs[lens_name] = 0.5
                continue

            sims = []
            for ex in pos_examples:
                pos_result = collection.query(
                    query_texts=[ex],
                    n_results=min(3, len(pos_examples)),
                    where={"$and": [{"lens": lens_name}, {"valence": "positive"}]},
                )
                pos_sim = 0.0
                if pos_result['distances'][0]:
                    for d in sorted(pos_result['distances'][0]):
                        s = 1 - d
                        if s < 0.999:
                            pos_sim = s
                            break

                neg_sim = 0.0
                if neg_examples:
                    neg_result = collection.query(
                        query_texts=[ex],
                        n_results=min(3, len(neg_examples)),
                        where={"$and": [{"lens": lens_name}, {"valence": "negative"}]},
                    )
                    if neg_result['distances'][0]:
                        neg_sim = 1 - min(neg_result['distances'][0])

                gap = pos_sim - neg_sim
                sims.append(max(gap, 0))

            cluster_avgs[lens_name] = sum(sims) / len(sims) if sims else 0.0

        eff = {p: cluster_avgs[p] * corrections[p] for p in PRIMARIES}
        vals = list(eff.values())
        diff = max(vals) - min(vals)

        print(f"    iter {iteration + 1}: " + " ".join(f"{p}={eff[p]:.4f}" for p in PRIMARIES) + f" diff={diff:.4f}")

        if diff < tolerance:
            print(f"    converged in {iteration + 1} iterations.")
            break

        if last_diff is not None:
            improvement = last_diff - diff
            if improvement < stall_threshold:
                stall_count += 1
                if stall_count >= 2:
                    print(f"    stalled after {iteration + 1} iterations. diff={diff:.4f}")
                    break
            else:
                stall_count = 0

        last_diff = diff

        target = sum(vals) / len(vals)
        for p in PRIMARIES:
            if eff[p] > 0:
                corrections[p] *= target / eff[p]

    converged = diff < tolerance

    print(f"    final corrections: " + " ".join(f"{p} x{corrections[p]:.4f}" for p in PRIMARIES))

    try:
        client.delete_collection("silverado_rgb_cal")
    except Exception:
        pass

    cal_meta = {
        "iterations": str(iteration + 1),
        "converged": str(converged),
        "final_diff": str(round(diff, 4)),
    }
    for p in PRIMARIES:
        cal_meta[f"{p}_correction"] = str(corrections[p])
        cal_meta[f"{p}_raw"] = str(cluster_avgs.get(p, 0.5))

    cal_collection = client.create_collection(name="silverado_rgb_cal", metadata=cal_meta)
    cal_collection.add(ids=["cal"], documents=["calibration"], metadatas=[{"type": "calibration"}])

    print(f"  calibration stored.")
    print(f"  lenses baked: {', '.join(sorted(lenses))}")


def bake_behavioral_detectors(examples_path=None):
    from keanu.abilities.world.compress.behavioral import BehavioralStore

    if examples_path is None:
        examples_path = DEFAULT_EXAMPLES

    if not Path(examples_path).exists():
        print(f"  {examples_path} not found. skipping detectors.")
        return

    print(f"  parsing {examples_path}...")
    examples = parse_reference_file(examples_path)

    detectors = set(e['detector'] for e in examples)
    print(f"  found {len(examples)} examples across {len(detectors)} detectors")

    store = BehavioralStore()
    bake_examples = [
        {"text": e["text"], "detector": e["detector"], "valence": e["valence"],
         "source": "silverado-bootstrap-v1"}
        for e in examples
    ]

    count = store.bake_collection("silverado", bake_examples)
    print(f"  baked {count} detector examples (behavioral)")
    print(f"  detectors baked: {', '.join(sorted(detectors))}")


def bake_behavioral_helix(lenses_path=None):
    from keanu.abilities.world.compress.behavioral import BehavioralStore

    if lenses_path is None:
        lenses_path = DEFAULT_LENSES

    if not Path(lenses_path).exists():
        print(f"  {lenses_path} not found. skipping helix.")
        return

    print(f"\n  parsing {lenses_path}...")
    examples = parse_lens_file(lenses_path)

    lenses = set(e['lens'] for e in examples)
    print(f"  found {len(examples)} examples across {len(lenses)} lenses")

    store = BehavioralStore()
    bake_examples = [
        {"text": e["text"], "lens": e["lens"], "valence": e["valence"],
         "source": "silverado-rgb-v1"}
        for e in examples
    ]

    count = store.bake_collection("silverado_rgb", bake_examples)
    print(f"  baked {count} lens examples (behavioral)")
    print(f"  lenses baked: {', '.join(sorted(lenses))}")


def bake(examples_path=None, lenses_path=None, detectors_only=False,
         helix_only=False, backend="chromadb"):
    if backend in ("chromadb", "both"):
        if not helix_only:
            bake_detectors(examples_path)
        if not detectors_only:
            bake_helix(lenses_path)

        # always bake abilities into chromadb
        from keanu.abilities.bake_abilities import bake_abilities
        bake_abilities()

        print(f"\n  done. chromadb vectors in {CHROMA_DIR}")

    if backend in ("behavioral", "both"):
        if not helix_only:
            bake_behavioral_detectors(examples_path)
        if not detectors_only:
            bake_behavioral_helix(lenses_path)
        from keanu.abilities.world.compress.behavioral import _get_behavioral_dir
        print(f"\n  done. behavioral vectors in {_get_behavioral_dir()}")
