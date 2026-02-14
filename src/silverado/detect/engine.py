"""
detect/engine.py - vector-based pattern detection.

positive vectors show what the pattern looks like.
negative vectors show the boundary of the pattern.
geometry sees what words alone can miss.
"""

import sys
import re
import json
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class Finding:
    category: str
    severity: str
    line_num: int
    text: str
    detail: str


@dataclass
class Report:
    filename: str
    total_lines: int
    findings: list[Finding] = field(default_factory=list)
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


def scan(lines, detector, threshold=0.65, high_threshold=0.75):
    """Query chromadb for a detector's vectors. Return findings."""
    try:
        import chromadb
    except ImportError:
        print("  pip install chromadb", file=sys.stderr)
        return []

    chroma_dir = _get_chroma_dir()
    if not Path(chroma_dir).exists():
        print("  no vectors found. run: silverado bake", file=sys.stderr)
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

    findings = []

    for line_num, text in scannable:
        pos_results = collection.query(
            query_texts=[text], n_results=3,
            where={"$and": [{"detector": detector}, {"valence": "positive"}]},
        )
        if not pos_results['distances'][0]:
            continue

        pos_sim = 1 - min(pos_results['distances'][0])
        if pos_sim < threshold:
            continue

        neg_results = collection.query(
            query_texts=[text], n_results=3,
            where={"$and": [{"detector": detector}, {"valence": "negative"}]},
        )

        neg_sim = 0.0
        if neg_results['distances'][0]:
            neg_sim = 1 - min(neg_results['distances'][0])

        gap = pos_sim - neg_sim
        if gap < 0.05:
            continue

        severity = "HIGH" if pos_sim >= high_threshold else "MEDIUM"
        findings.append(Finding(
            category=detector, severity=severity,
            line_num=line_num, text=text[:120],
            detail=f"positive: {pos_sim:.3f}, negative: {neg_sim:.3f}, gap: {gap:.3f}",
        ))

    return findings


def score_report(report):
    high = sum(1 for f in report.findings if f.severity == "HIGH")
    med = sum(1 for f in report.findings if f.severity == "MEDIUM")
    lines = max(report.total_lines, 1)
    density = (high * 3 + med) / lines * 100
    report.score = round(min(10, density), 1)


def format_report(report, title="SCAN"):
    out = [
        f"== {title}: {report.filename} ==",
        f"  {report.total_lines} lines, {len(report.findings)} hits",
        f"  score: {report.score}/10",
        "",
    ]

    if not report.findings:
        out.append("  clean.")
        return "\n".join(out)

    by_cat = defaultdict(list)
    for f in report.findings:
        by_cat[f.category].append(f)

    for cat in sorted(by_cat.keys()):
        items = sorted(by_cat[cat], key=lambda f: (f.severity != "HIGH", f.severity != "MEDIUM"))
        out.append(f"-- {cat} ({len(items)}) --")
        for f in items:
            marker = {"HIGH": "🔴", "MEDIUM": "🟡"}.get(f.severity, "⚪")
            out.append(f"  {marker} L{f.line_num}: {f.text[:80]}")
            out.append(f"     {f.detail}")
        out.append("")

    return "\n".join(out)


def run(filepath, detector, title="SCAN", output_json=False):
    if filepath == "-":
        text = sys.stdin.read()
        filename = "stdin"
    else:
        with open(filepath) as f:
            text = f.read()
        filename = filepath

    lines = text.split("\n")
    report = Report(filename=filename, total_lines=len(lines))
    report.findings.extend(scan(lines, detector))
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
