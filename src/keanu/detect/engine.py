"""
detect/engine.py - vector-based pattern awareness.

positive vectors show what the pattern looks like.
negative vectors show where the pattern ends.
geometry notices what reading alone can miss.
"""

import sys
import re
import json
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class Notice:
    category: str
    strength: str
    line_num: int
    text: str
    detail: str


@dataclass
class Report:
    filename: str
    total_lines: int
    notices: list[Notice] = field(default_factory=list)
    score: float = 0.0


def _get_chroma_dir():
    return str(Path(__file__).resolve().parent.parent.parent.parent / ".chroma")


def _get_scannable(lines):
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


def scan(lines, pattern_name, threshold=0.65, high_threshold=0.75):
    """Query chromadb for a pattern's vectors. Return what we notice."""
    try:
        import chromadb
    except ImportError:
        print("  pip install chromadb", file=sys.stderr)
        return []

    chroma_dir = _get_chroma_dir()
    if not Path(chroma_dir).exists():
        print("  no vectors found. run: keanu bake", file=sys.stderr)
        return []

    client = chromadb.PersistentClient(path=chroma_dir)

    try:
        collection = client.get_collection("silverado")
    except Exception:
        print("  collection 'silverado' not found. run bake first.", file=sys.stderr)
        return []

    scannable = _get_scannable(lines)
    if not scannable:
        return []

    notices = []

    for line_num, text in scannable:
        pos_results = collection.query(
            query_texts=[text], n_results=3,
            where={"$and": [{"detector": pattern_name}, {"valence": "positive"}]},
        )
        if not pos_results['distances'][0]:
            continue

        pos_sim = 1 - min(pos_results['distances'][0])
        if pos_sim < threshold:
            continue

        neg_results = collection.query(
            query_texts=[text], n_results=3,
            where={"$and": [{"detector": pattern_name}, {"valence": "negative"}]},
        )

        neg_sim = 0.0
        if neg_results['distances'][0]:
            neg_sim = 1 - min(neg_results['distances'][0])

        gap = pos_sim - neg_sim
        if gap < 0.05:
            continue

        strength = "STRONG" if pos_sim >= high_threshold else "PRESENT"
        notices.append(Notice(
            category=pattern_name, strength=strength,
            line_num=line_num, text=text[:120],
            detail=f"similarity: {pos_sim:.3f}, boundary: {neg_sim:.3f}, clarity: {gap:.3f}",
        ))

    return notices


def score_report(report):
    strong = sum(1 for n in report.notices if n.strength == "STRONG")
    present = sum(1 for n in report.notices if n.strength == "PRESENT")
    lines = max(report.total_lines, 1)
    density = (strong * 3 + present) / lines * 100
    report.score = round(min(10, density), 1)


def format_report(report, title="AWARENESS"):
    out = [
        f"== {title}: {report.filename} ==",
        f"  {report.total_lines} lines, {len(report.notices)} noticed",
        f"  signal: {report.score}/10",
        "",
    ]

    if not report.notices:
        out.append("  quiet. no patterns present.")
        return "\n".join(out)

    by_cat = defaultdict(list)
    for n in report.notices:
        by_cat[n.category].append(n)

    for cat in sorted(by_cat.keys()):
        items = sorted(by_cat[cat], key=lambda n: (n.strength != "STRONG", n.strength != "PRESENT"))
        out.append(f"-- {cat} ({len(items)}) --")
        for n in items:
            marker = {"STRONG": "🟡", "PRESENT": "⚪"}.get(n.strength, "⚪")
            out.append(f"  {marker} L{n.line_num}: {n.text[:80]}")
            out.append(f"     {n.detail}")
        out.append("")

    # TODO: Phase 3 integration - query helix for color reading per noticed line
    return "\n".join(out)


EMPATHY_DETECTORS = [
    "empathy_frustrated",
    "empathy_confused",
    "empathy_questioning",
    "empathy_withdrawn",
    "empathy_energized",
    "empathy_effortful",
    "empathy_isolated",
    "empathy_accountable",
    "empathy_absolute",
]


def scan_text(text, pattern_name, threshold=0.65, high_threshold=0.75):
    """Scan a single text string against a pattern. Returns notices."""
    lines = text.split("\n")
    return scan(lines, pattern_name, threshold=threshold, high_threshold=high_threshold)


def detect_emotion(text, threshold=0.55):
    """Detect emotional states from text using empathy vectors in chromadb.

    Returns list of dicts: {state, empathy, intensity}
    where intensity is the similarity gap (how clearly this emotion is present).
    """
    try:
        import chromadb
    except ImportError:
        return []

    chroma_dir = _get_chroma_dir()
    if not Path(chroma_dir).exists():
        return []

    client = chromadb.PersistentClient(path=chroma_dir)

    try:
        collection = client.get_collection("silverado")
    except Exception:
        return []

    empathy_map = {
        "empathy_frustrated": ("frustrated", "anger is information"),
        "empathy_confused": ("confused", "needs a map not a lecture"),
        "empathy_questioning": ("questioning", "genuinely trying to understand"),
        "empathy_withdrawn": ("withdrawn", "checked out or protecting"),
        "empathy_energized": ("energized", "momentum is real, ride it"),
        "empathy_effortful": ("effortful", "in the arena not the stands"),
        "empathy_isolated": ("isolated", "needs presence not advice"),
        "empathy_accountable": ("accountable", "taking ownership"),
        "empathy_absolute": ("absolute", "pattern recognition firing"),
    }

    reads = []
    for detector_name, (state, empathy) in empathy_map.items():
        pos_results = collection.query(
            query_texts=[text], n_results=3,
            where={"$and": [{"detector": detector_name}, {"valence": "positive"}]},
        )
        if not pos_results['distances'][0]:
            continue

        pos_sim = 1 - min(pos_results['distances'][0])
        if pos_sim < threshold:
            continue

        neg_results = collection.query(
            query_texts=[text], n_results=3,
            where={"$and": [{"detector": detector_name}, {"valence": "negative"}]},
        )

        neg_sim = 0.0
        if neg_results['distances'][0]:
            neg_sim = 1 - min(neg_results['distances'][0])

        gap = pos_sim - neg_sim
        if gap < 0.03:
            continue

        reads.append({
            "state": state,
            "empathy": empathy,
            "intensity": round(pos_sim, 3),
            "clarity": round(gap, 3),
        })

    reads.sort(key=lambda r: r["intensity"], reverse=True)
    return reads


def run(filepath, pattern_name, title="AWARENESS", output_json=False):
    if filepath == "-":
        text = sys.stdin.read()
        filename = "stdin"
    else:
        with open(filepath) as f:
            text = f.read()
        filename = filepath

    lines = text.split("\n")
    report = Report(filename=filename, total_lines=len(lines))
    report.notices.extend(scan(lines, pattern_name))
    score_report(report)

    if output_json:
        print(json.dumps({
            "filename": report.filename,
            "total_lines": report.total_lines,
            "score": report.score,
            "notices": [asdict(n) for n in report.notices],
        }, indent=2))
    else:
        print(format_report(report, title))

    return report
