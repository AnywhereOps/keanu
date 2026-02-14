"""
connection.py - the space between two sources.

one source has signal. another source has signal.
where they overlap = common ground. start there.
where one has signal the other doesn't = room to grow.
"""

import sys
from dataclasses import dataclass, field


@dataclass
class CommonGround:
    line_a: int
    text_a: str
    line_b: int
    text_b: str
    similarity: float


@dataclass
class Gap:
    source: str
    line_num: int
    text: str
    primary: str
    strength: float


@dataclass
class AlignmentReport:
    source_a: str
    source_b: str
    common_ground: list[CommonGround] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    alignment_score: float = 0.0


def align(filepath_a, filepath_b, threshold=0.7):
    """Read two files through the helix. Find where they meet and where they diverge."""
    from silverado.scan.helix import helix_scan

    text_a = _read(filepath_a)
    text_b = _read(filepath_b)

    result_a = helix_scan(text_a.split("\n"))
    result_b = helix_scan(text_b.split("\n"))

    if result_a is None or result_b is None:
        return AlignmentReport(source_a=filepath_a, source_b=filepath_b)

    readings_a, _, tensions_a = result_a
    readings_b, _, tensions_b = result_b

    common = _find_overlap(readings_a, readings_b, threshold)
    gaps = _find_unique(tensions_a, "A") + _find_unique(tensions_b, "B")
    gaps.sort(key=lambda g: -g.strength)

    total = len(set(r.line_num for r in readings_a) | set(r.line_num for r in readings_b))
    score = len(common) / total * 10 if total > 0 else 0

    return AlignmentReport(
        source_a=filepath_a,
        source_b=filepath_b,
        common_ground=common,
        gaps=gaps[:10],
        alignment_score=round(min(score, 10), 1),
    )


def _read(filepath):
    if filepath == "-":
        return sys.stdin.read()
    with open(filepath) as f:
        return f.read()


def _find_overlap(readings_a, readings_b, threshold):
    """Embed A's readings, query with B's. Semantic overlap above threshold = common ground."""
    try:
        import chromadb
    except ImportError:
        return []

    if not readings_a or not readings_b:
        return []

    client = chromadb.EphemeralClient()
    col = client.create_collection("alignment", metadata={"hnsw:space": "cosine"})

    col.add(
        ids=[f"a_{r.line_num}" for r in readings_a],
        documents=[r.text for r in readings_a],
        metadatas=[{"line_num": r.line_num} for r in readings_a],
    )

    common = []
    for r_b in readings_b:
        results = col.query(query_texts=[r_b.text], n_results=1)
        if not results["distances"][0]:
            continue
        sim = 1 - results["distances"][0][0]
        if sim >= threshold:
            ln_a = results["metadatas"][0][0]["line_num"]
            a_text = next((r.text for r in readings_a if r.line_num == ln_a), "")
            common.append(CommonGround(
                line_a=ln_a, text_a=a_text,
                line_b=r_b.line_num, text_b=r_b.text,
                similarity=round(sim, 3),
            ))

    return sorted(common, key=lambda c: -c.similarity)


def _find_unique(tensions, label):
    """Tensions in one source are signal the other source doesn't have yet."""
    return [
        Gap(
            source=label,
            line_num=t.line_num,
            text=t.text,
            primary=t.dominant,
            strength=round(t.gap, 3),
        )
        for t in tensions
    ]


def format_alignment(report):
    out = [
        f"== ALIGNMENT ==",
        f"  A: {report.source_a}",
        f"  B: {report.source_b}",
        f"  alignment: {report.alignment_score}/10",
        "",
    ]

    if report.common_ground:
        out.append(f"-- COMMON GROUND ({len(report.common_ground)}) --")
        for cg in report.common_ground[:5]:
            out.append(f"  A:L{cg.line_a} + B:L{cg.line_b}  (sim: {cg.similarity})")
            out.append(f"    \"{cg.text_a[:60]}\"")
            out.append(f"    \"{cg.text_b[:60]}\"")
        out.append("")

    if report.gaps:
        out.append(f"-- UNIQUE SIGNAL ({len(report.gaps)}) --")
        for g in report.gaps[:5]:
            out.append(f"  {g.source}:L{g.line_num} ({g.primary}, strength: {g.strength})")
            out.append(f"    \"{g.text[:60]}\"")
        out.append("")

    return "\n".join(out)


def run(filepath_a, filepath_b):
    report = align(filepath_a, filepath_b)
    print(format_alignment(report))
    return report
