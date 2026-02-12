#!/usr/bin/env python3
"""
the brain in the truck bed.
vectors in chromadb. no strings at runtime. pure math.
positive vectors say "this is the pattern."
negative vectors say "this is NOT the pattern, even though it looks close."
the geometry captures what regex never could.

  from tools.coef_engine import run
  run('file.md', detector='sycophancy', title='SYCOPHANCY SCAN')
"""

import sys
import os
import re
import json
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '.chroma'))


@dataclass
class Finding:
    category: str
    severity: str
    line_num: int
    text: str
    detail: str
    line_num_2: Optional[int] = None
    text_2: Optional[str] = None


@dataclass
class Report:
    filename: str
    total_lines: int
    findings: list = field(default_factory=list)
    score: float = 0.0

    def add(self, f: Finding):
        self.findings.append(f)


def coef_scan(lines, detector, threshold=0.65, high_threshold=0.75):
    """
    query chromadb for this detector's vectors.
    for each prose line: how close to the positive examples? how far from the negatives?
    if close to positive AND far from negative: flag it.
    """
    try:
        import chromadb
    except ImportError:
        print("  pip install chromadb", file=sys.stderr)
        return []

    if not os.path.exists(CHROMA_DIR):
        print("  no vectors found. run: python3 silverado.py bake", file=sys.stderr)
        return []

    client = chromadb.PersistentClient(path=CHROMA_DIR)

    try:
        collection = client.get_collection("silverado")
    except Exception:
        print("  collection 'silverado' not found. run bake.py first.", file=sys.stderr)
        return []

    scannable = []
    for i, line in enumerate(lines):
        s = line.strip()
        if (len(s) < 20
                or s.startswith(("#", "```", "import ", "from ", "def ", "class "))
                or re.match(r'^[\s\-\|=\+\*`#>]+$', s)
                or re.match(r'^r["\']', s)):
            continue
        scannable.append((i + 1, s))

    if not scannable:
        return []

    texts = [t for _, t in scannable]
    print(f"  scanning {len(texts)} lines against {detector}...", file=sys.stderr)

    findings = []

    for line_num, text in scannable:
        pos_results = collection.query(
            query_texts=[text],
            n_results=3,
            where={"$and": [{"detector": detector}, {"valence": "positive"}]},
        )

        if not pos_results['distances'][0]:
            continue

        pos_distances = pos_results['distances'][0]
        pos_sim = 1 - min(pos_distances)

        if pos_sim < threshold:
            continue

        neg_results = collection.query(
            query_texts=[text],
            n_results=3,
            where={"$and": [{"detector": detector}, {"valence": "negative"}]},
        )

        neg_sim = 0.0
        if neg_results['distances'][0]:
            neg_distances = neg_results['distances'][0]
            neg_sim = 1 - min(neg_distances)

        gap = pos_sim - neg_sim
        if gap < 0.05:
            continue

        severity = "HIGH" if pos_sim >= high_threshold else "MEDIUM"
        findings.append(Finding(
            category=detector,
            severity=severity,
            line_num=line_num,
            text=text[:120],
            detail=f"positive: {pos_sim:.3f}, negative: {neg_sim:.3f}, gap: {gap:.3f}",
        ))

    return findings


def score_report(report):
    """0 = honest. 10 = press release."""
    high = sum(1 for f in report.findings if f.severity == "HIGH")
    med = sum(1 for f in report.findings if f.severity == "MEDIUM")
    lines = max(report.total_lines, 1)
    density = (high * 3 + med) / lines * 100
    report.score = round(min(10, density), 1)


def format_report(report, title="SCAN"):
    out = []
    out.append(f"╔══ {title}: {report.filename} ══╗")
    out.append(f"  {report.total_lines} lines, {len(report.findings)} hits")
    out.append(f"  score: {report.score}/10")
    out.append(f"╚{'═' * 45}╝\n")

    if not report.findings:
        out.append("  ✅ clean. nothing stinks.")
        return "\n".join(out)

    by_cat = defaultdict(list)
    for f in report.findings:
        by_cat[f.category].append(f)

    sev = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    for cat in sorted(by_cat.keys()):
        items = sorted(by_cat[cat], key=lambda f: sev.get(f.severity, 3))
        out.append(f"── {cat} ({len(items)}) ──")
        for f in items:
            marker = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "⚪"}.get(f.severity, "?")
            out.append(f"  {marker} L{f.line_num}: {f.text[:80]}")
            if f.line_num_2:
                out.append(f"     vs L{f.line_num_2}: {f.text_2[:80]}")
            out.append(f"     {f.detail}")
        out.append("")

    return "\n".join(out)


def run(filepath, detector, title="SCAN", threshold=0.65, high_threshold=0.75, output_json=False):
    """point it at a file and a detector name. it tells you what reeks."""
    if filepath == "-":
        text = sys.stdin.read()
        filename = "stdin"
    else:
        with open(filepath, "r") as f:
            text = f.read()
        filename = filepath

    lines = text.split("\n")
    report = Report(filename=filename, total_lines=len(lines))
    report.findings.extend(coef_scan(lines, detector, threshold, high_threshold))
    score_report(report)

    if output_json:
        print(json.dumps({
            "filename": report.filename,
            "total_lines": report.total_lines,
            "score": report.score,
            "findings": [asdict(f) for f in report.findings],
        }, indent=2))
    else:
        print(format_report(report, title))

    return report
