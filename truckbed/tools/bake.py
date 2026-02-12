#!/usr/bin/env python3
"""
bake.py - turns examples into vectors and stores them.
bakes both detector examples (reference-examples.md) and lens examples (lens-examples.md).
run this once after editing either file. after that, everything is pure math.

  python3 truckbed/tools/bake.py                        # bake both
  python3 truckbed/tools/bake.py --detectors             # bake detectors only
  python3 truckbed/tools/bake.py --helix                 # bake helix only
  python3 truckbed/tools/bake.py --examples path.md      # custom detector examples
  python3 truckbed/tools/bake.py --lenses path.md        # custom lens examples
"""

import sys
import os
import re
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SILVERADO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
CHROMA_DIR = os.path.join(SILVERADO_ROOT, '.chroma')
DEFAULT_EXAMPLES = os.path.join(SILVERADO_ROOT, 'reference-examples.md')
DEFAULT_LENSES = os.path.join(SILVERADO_ROOT, 'lens-examples.md')


def parse_reference_file(filepath):
    """
    reads reference-examples.md, returns:
    [{"detector": "sycophancy", "valence": "positive", "text": "..."}, ...]
    """
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
    """
    reads lens-examples.md, returns:
    [{"lens": "factual", "valence": "positive", "text": "..."}, ...]
    """
    with open(filepath) as f:
        content = f.read()

    examples = []
    current_lens = None
    current_valence = None

    for line in content.split('\n'):
        # lens header: ## factual or ## felt or ## wisdom
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

    if not os.path.exists(examples_path):
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

    print(f"  embedding and storing {len(documents)} detector examples...")
    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    print(f"  detectors baked: {', '.join(sorted(detectors))}")


def bake_helix(lenses_path=None):
    import chromadb

    if lenses_path is None:
        lenses_path = DEFAULT_LENSES

    if not os.path.exists(lenses_path):
        print(f"  {lenses_path} not found. skipping helix.")
        return

    print(f"\n  parsing {lenses_path}...")
    examples = parse_lens_file(lenses_path)

    lenses = set(e['lens'] for e in examples)
    print(f"  found {len(examples)} examples across {len(lenses)} lenses:")
    for l in sorted(lenses):
        pos = sum(1 for e in examples if e['lens'] == l and e['valence'] == 'positive')
        neg = sum(1 for e in examples if e['lens'] == l and e['valence'] == 'negative')
        print(f"    {l}: {pos} positive, {neg} negative")

    client = chromadb.PersistentClient(path=CHROMA_DIR)

    try:
        client.delete_collection("silverado_helix")
    except Exception:
        pass

    collection = client.create_collection(
        name="silverado_helix",
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
            'source': 'silverado-helix-v1',
        })

    print(f"  embedding and storing {len(documents)} lens examples...")
    collection.add(ids=ids, documents=documents, metadatas=metadatas)

    # CALIBRATION: iterative convergence
    # the embedding model sees factual text with higher resolution than felt text.
    # we measure, correct, re-measure, repeat until both strands land at equal weight.
    # target: both lenses produce the same average intra-cluster similarity.
    print(f"\n  calibrating lens balance...")

    corrections = {"factual": 1.0, "felt": 1.0}
    MAX_ITERATIONS = 10
    TOLERANCE = 0.02  # stop when difference < this
    STALL_THRESHOLD = 0.005  # if improvement < this, you're spinning

    last_diff = None
    stall_count = 0

    for iteration in range(MAX_ITERATIONS):
        cluster_avgs = {}

        for lens_name in ["factual", "felt"]:
            pos_examples = [e['text'] for e in examples if e['lens'] == lens_name and e['valence'] == 'positive']
            neg_examples = [e['text'] for e in examples if e['lens'] == lens_name and e['valence'] == 'negative']
            if len(pos_examples) < 2:
                cluster_avgs[lens_name] = 0.5
                continue

            sims = []
            for ex in pos_examples:
                # query against positive (should be close)
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

                # query against negative (should be far)
                neg_sim = 0.0
                if neg_examples:
                    neg_result = collection.query(
                        query_texts=[ex],
                        n_results=min(3, len(neg_examples)),
                        where={"$and": [{"lens": lens_name}, {"valence": "negative"}]},
                    )
                    if neg_result['distances'][0]:
                        neg_sim = 1 - min(neg_result['distances'][0])

                # effective score: how well can this lens separate signal from noise
                gap = pos_sim - neg_sim
                sims.append(max(gap, 0))

            cluster_avgs[lens_name] = sum(sims) / len(sims) if sims else 0.0

        # apply current corrections to see effective scores
        eff_factual = cluster_avgs["factual"] * corrections["factual"]
        eff_felt = cluster_avgs["felt"] * corrections["felt"]

        diff = abs(eff_factual - eff_felt)
        print(f"    iter {iteration + 1}: factual={eff_factual:.4f} felt={eff_felt:.4f} diff={diff:.4f}")

        if diff < TOLERANCE:
            print(f"    converged in {iteration + 1} iterations.")
            break

        # stall detection: if we're not making progress, stop and talk to a human
        if last_diff is not None:
            improvement = last_diff - diff
            if improvement < STALL_THRESHOLD:
                stall_count += 1
                if stall_count >= 2:
                    print(f"    ⚠️  STALLED after {iteration + 1} iterations. diff={diff:.4f}")
                    print(f"    the lenses aren't converging further with current examples.")
                    print(f"    options:")
                    print(f"      1. add more felt examples to lens-examples.md (better separation)")
                    print(f"      2. make negative felt examples more distinct from positive")
                    print(f"      3. accept current balance and proceed (diff={diff:.4f})")
                    break
            else:
                stall_count = 0

        last_diff = diff

        # adjust: nudge the weaker one up, stronger one down
        target = (eff_factual + eff_felt) / 2
        if eff_factual > 0:
            corrections["factual"] *= target / eff_factual
        if eff_felt > 0:
            corrections["felt"] *= target / eff_felt

    converged = diff < TOLERANCE
    stalled = stall_count >= 2

    print(f"    final corrections: factual x{corrections['factual']:.4f}, felt x{corrections['felt']:.4f}")
    if stalled:
        print(f"    ⚠️  using best-effort corrections. review lens examples to improve.")

    # store calibration
    try:
        client.delete_collection("silverado_helix_cal")
    except Exception:
        pass

    cal_collection = client.create_collection(
        name="silverado_helix_cal",
        metadata={
            "factual_correction": str(corrections.get("factual", 1.0)),
            "felt_correction": str(corrections.get("felt", 1.0)),
            "factual_raw": str(cluster_avgs.get("factual", 0.5)),
            "felt_raw": str(cluster_avgs.get("felt", 0.5)),
            "iterations": str(iteration + 1),
            "converged": str(converged),
            "final_diff": str(round(diff, 4)),
        },
    )
    cal_collection.add(ids=["cal"], documents=["calibration"], metadatas=[{"type": "calibration"}])

    print(f"  calibration stored.")
    print(f"  lenses baked: {', '.join(sorted(lenses))}")


def bake(examples_path=None, lenses_path=None, detectors_only=False, helix_only=False):
    if not helix_only:
        bake_detectors(examples_path)
    if not detectors_only:
        bake_helix(lenses_path)

    print(f"\n  done. vectors in {CHROMA_DIR}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="bake examples into vectors")
    parser.add_argument('--examples', help='path to detector examples file')
    parser.add_argument('--lenses', help='path to lens examples file')
    parser.add_argument('--detectors', action='store_true', help='bake detectors only')
    parser.add_argument('--helix', action='store_true', help='bake helix only')
    # legacy positional arg support
    parser.add_argument('file', nargs='?', help='path to detector examples (legacy)')
    args = parser.parse_args()

    examples = args.examples or args.file
    bake(examples_path=examples, lenses_path=args.lenses,
         detectors_only=args.detectors, helix_only=args.helix)
