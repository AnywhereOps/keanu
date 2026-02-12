#!/usr/bin/env python3
"""
helix.py - the double strand.
strand A: what is factually true in this text?
strand B: what does this text actually mean/care about?
convergence: where both point the same direction = wisdom
tension: where they disagree = signal worth investigating

same chromadb backend as coef_engine. different collection. different question.
coef_engine asks "does this stink?" helix asks "what's real?"

  from tools.helix import helix_scan, run
  run('file.md', title='HELIX SCAN')
"""

import sys
import os
import re
import json
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Optional, List

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', '.chroma'))


@dataclass
class Strand:
    line_num: int
    text: str
    lens: str           # "factual" or "felt"
    strength: float     # 0-1 how strongly this registers
    detail: str


@dataclass
class Convergence:
    line_num: int
    text: str
    factual_strength: float
    felt_strength: float
    wisdom_score: float  # min(factual, felt) - both present = wisdom
    detail: str


@dataclass
class Tension:
    line_num: int
    text: str
    factual_strength: float
    felt_strength: float
    gap: float          # abs difference - high gap = interesting
    dominant: str       # which strand is stronger
    detail: str


@dataclass
class HelixReport:
    filename: str
    total_lines: int
    factual_strands: List[Strand] = field(default_factory=list)
    felt_strands: List[Strand] = field(default_factory=list)
    convergences: List[Convergence] = field(default_factory=list)
    tensions: List[Tension] = field(default_factory=list)
    mood: dict = field(default_factory=lambda: {"factual": 0, "felt": 0, "wise": 0, "black_flag": False, "nudge": ""})
    factual_avg: float = 0.0
    felt_avg: float = 0.0
    wisdom_score: float = 0.0


def _get_scannable(lines):
    """filter to prose lines worth scanning."""
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


def _query_lens(collection, text, lens, n=3):
    """query one lens, return best similarity."""
    pos = collection.query(
        query_texts=[text],
        n_results=n,
        where={"$and": [{"lens": lens}, {"valence": "positive"}]},
    )
    if not pos['distances'][0]:
        return 0.0

    pos_sim = 1 - min(pos['distances'][0])

    neg = collection.query(
        query_texts=[text],
        n_results=n,
        where={"$and": [{"lens": lens}, {"valence": "negative"}]},
    )
    neg_sim = 0.0
    if neg['distances'][0]:
        neg_sim = 1 - min(neg['distances'][0])

    # only count if clearly closer to positive than negative
    gap = pos_sim - neg_sim
    if gap < 0.03:
        return 0.0

    return pos_sim


def helix_scan(lines, factual_threshold=0.55, felt_threshold=0.55,
               factual_accel=None, felt_accel=None):
    """
    dual-lens scan. one embedding pass per line, two queries (factual + felt).
    returns strands, convergences, and tensions.

    accelerators (optional):
      factual_accel / felt_accel: multiplier the consumer chooses.
      None = use calibration from bake (corrects for model bias).
      1.0 = raw scores, no correction.
      >1.0 = amplify this strand.
      <1.0 = dampen this strand.
      the tool doesn't decide what balance means. you do.
    """
    try:
        import chromadb
    except ImportError:
        print("  pip install chromadb", file=sys.stderr)
        return None

    if not os.path.exists(CHROMA_DIR):
        print("  no vectors found. run: python3 silverado.py bake", file=sys.stderr)
        return None

    client = chromadb.PersistentClient(path=CHROMA_DIR)

    try:
        collection = client.get_collection("silverado_helix")
    except Exception:
        print("  collection 'silverado_helix' not found. run: python3 silverado.py bake", file=sys.stderr)
        return None

    # load calibration corrections (measured at bake time)
    # these correct for the model's natural bias toward factual text.
    # but the consumer can override with their own accelerators.
    f_correction = 1.0
    e_correction = 1.0
    cal_converged = True

    try:
        cal = client.get_collection("silverado_helix_cal")
        cal_f = float(cal.metadata.get("factual_correction", "1.0"))
        cal_e = float(cal.metadata.get("felt_correction", "1.0"))
        cal_converged = cal.metadata.get("converged", "True") == "True"
        final_diff = cal.metadata.get("final_diff", "0")

        # consumer overrides calibration if they have an opinion
        if factual_accel is not None:
            f_correction = factual_accel
        else:
            f_correction = cal_f

        if felt_accel is not None:
            e_correction = felt_accel
        else:
            e_correction = cal_e

        mode = []
        if factual_accel is not None or felt_accel is not None:
            mode.append("consumer-set")
        else:
            mode.append("auto-calibrated")
        if not cal_converged:
            mode.append("cal-incomplete")

        print(f"  [{', '.join(mode)}] factual x{f_correction:.3f}, felt x{e_correction:.3f}", file=sys.stderr)

    except Exception:
        # no calibration exists. use consumer values or raw.
        f_correction = factual_accel if factual_accel is not None else 1.0
        e_correction = felt_accel if felt_accel is not None else 1.0
        print(f"  [raw] no calibration found. factual x{f_correction:.3f}, felt x{e_correction:.3f}", file=sys.stderr)
    except Exception:
        print("  no calibration found, using raw scores (run: silverado.py bake)", file=sys.stderr)

    scannable = _get_scannable(lines)
    if not scannable:
        return None

    print(f"  helix scanning {len(scannable)} lines...", file=sys.stderr)

    factual_strands = []
    felt_strands = []
    convergences = []
    tensions = []

    for line_num, text in scannable:
        # one line, two queries. that's the helix.
        f_score = _query_lens(collection, text, "factual") * f_correction
        e_score = _query_lens(collection, text, "felt") * e_correction

        # cap at 1.0 after correction
        f_score = min(f_score, 1.0)
        e_score = min(e_score, 1.0)

        # record strands
        if f_score >= factual_threshold:
            factual_strands.append(Strand(
                line_num=line_num, text=text[:120], lens="factual",
                strength=f_score, detail=f"factual: {f_score:.3f}",
            ))

        if e_score >= felt_threshold:
            felt_strands.append(Strand(
                line_num=line_num, text=text[:120], lens="felt",
                strength=e_score, detail=f"felt: {e_score:.3f}",
            ))

        # convergence: both strands present and strong
        if f_score >= factual_threshold and e_score >= felt_threshold:
            wisdom = min(f_score, e_score)  # wisdom = weakest strong strand
            convergences.append(Convergence(
                line_num=line_num, text=text[:120],
                factual_strength=f_score, felt_strength=e_score,
                wisdom_score=wisdom,
                detail=f"factual: {f_score:.3f}, felt: {e_score:.3f}, wisdom: {wisdom:.3f}",
            ))

        # tension: one strand strong, other weak or absent
        if (f_score >= factual_threshold) != (e_score >= felt_threshold):
            gap = abs(f_score - e_score)
            dominant = "factual" if f_score > e_score else "felt"
            tensions.append(Tension(
                line_num=line_num, text=text[:120],
                factual_strength=f_score, felt_strength=e_score,
                gap=gap, dominant=dominant,
                detail=f"factual: {f_score:.3f}, felt: {e_score:.3f}, gap: {gap:.3f}, leans: {dominant}",
            ))

    return factual_strands, felt_strands, convergences, tensions


def mood_elevator(factual_avg, felt_avg):
    """
    three numbers. 0-10 each.

    factual mind:  how strongly is truth present?
    felt mind:     how strongly is meaning present?
    wise mind:     min(factual, felt). both have to show up.

    wise mind can never be higher than either strand.
    that's the whole point. wisdom isn't an average. it's a floor.
    """
    f_score = round(min(factual_avg * 10, 10), 1)
    e_score = round(min(felt_avg * 10, 10), 1)
    w_score = round(min(f_score, e_score), 1)

    # black risk: factual strong, felt in the fake zone
    black_flag = False
    if factual_avg > 0.5 and 0.15 <= felt_avg <= 0.35:
        black_flag = True

    # nudge
    if w_score >= 7:
        nudge = "both strands sharp."
    elif abs(f_score - e_score) < 1.5:
        nudge = "balanced. build both."
    elif f_score > e_score + 2:
        nudge = "facts ahead. what does this mean to someone?"
    elif e_score > f_score + 2:
        nudge = "feeling ahead. what's actually true here?"
    elif w_score < 2:
        nudge = "thin signal."
    else:
        nudge = "getting there."

    if black_flag:
        nudge = "⚠️ felt may be performing. check tensions."

    return {
        "factual": f_score,
        "felt": e_score,
        "wise": w_score,
        "black_flag": black_flag,
        "nudge": nudge,
    }


def format_helix_report(report, title="HELIX SCAN"):
    out = []
    mood = report.mood
    out.append(f"╔══ {title}: {report.filename} ══╗")
    out.append(f"  {report.total_lines} lines")
    out.append(f"  factual: {mood['factual']}  felt: {mood['felt']}  wise: {mood['wise']}")
    out.append(f"  {mood['nudge']}")
    out.append(f"  convergences: {len(report.convergences)}  tensions: {len(report.tensions)}")
    out.append(f"╚{'═' * 45}╝\n")

    if report.convergences:
        out.append("── WISDOM (both strands align) ──")
        for c in sorted(report.convergences, key=lambda x: -x.wisdom_score)[:10]:
            out.append(f"  ✓ L{c.line_num}: {c.text[:80]}")
            out.append(f"     {c.detail}")
        out.append("")

    if report.tensions:
        out.append("── TENSIONS (one strand missing, nudge included) ──")
        for t in sorted(report.tensions, key=lambda x: -x.gap)[:10]:
            if t.dominant == "factual":
                nudge = "↑ felt: what does this mean to someone?"
            else:
                nudge = "↑ factual: what evidence supports this?"
            out.append(f"  → L{t.line_num}: {t.text[:80]}")
            out.append(f"     {t.detail}")
            out.append(f"     {nudge}")
        out.append("")

    if not report.convergences and not report.tensions:
        out.append("  ⚪ no strong signal either direction.")

    return "\n".join(out)


def run(filepath, title="HELIX SCAN", output_json=False,
        factual_accel=None, felt_accel=None):
    """point it at a file. it tells you what's true and what it means."""
    if filepath == "-":
        text = sys.stdin.read()
        filename = "stdin"
    else:
        with open(filepath, "r") as f:
            text = f.read()
        filename = filepath

    lines = text.split("\n")
    result = helix_scan(lines, factual_accel=factual_accel, felt_accel=felt_accel)

    if result is None:
        report = HelixReport(filename=filename, total_lines=len(lines))
    else:
        factual_strands, felt_strands, convergences, tensions = result
        report = HelixReport(
            filename=filename,
            total_lines=len(lines),
            factual_strands=factual_strands,
            felt_strands=felt_strands,
            convergences=convergences,
            tensions=tensions,
        )

        # averages across all scanned lines
        f_scores = [s.strength for s in factual_strands] or [0]
        e_scores = [s.strength for s in felt_strands] or [0]
        report.factual_avg = sum(f_scores) / max(len(f_scores), 1)
        report.felt_avg = sum(e_scores) / max(len(e_scores), 1)
        report.wisdom_score = round(min(report.factual_avg, report.felt_avg), 2)
        report.mood = mood_elevator(report.factual_avg, report.felt_avg)

    if output_json:
        print(json.dumps({
            "filename": report.filename,
            "total_lines": report.total_lines,
            "factual_avg": report.factual_avg,
            "felt_avg": report.felt_avg,
            "wisdom_score": report.wisdom_score,
            "mood": report.mood,
            "convergences": [asdict(c) for c in report.convergences],
            "tensions": [asdict(t) for t in report.tensions],
        }, indent=2))
    else:
        print(format_helix_report(report, title))

    return report
