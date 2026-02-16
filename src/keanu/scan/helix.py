"""
helix.py - the triple strand.

three primaries. each has two poles.
  red:    passion (+) vs rage (-)
  yellow: awareness (+) vs fear (-)
  blue:   depth (+) vs cold (-)

convergence: multiple primaries strong in same line = rich signal
tension: one primary dominates, others absent = investigate

where all three fires burn = white (alive)
where all three are ash = black (frankenstein)
where fire and ash balance = sunrise (wisdom)

collection: silverado_rgb
"""

import sys
import re
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

PRIMARIES = ("red", "yellow", "blue")


from keanu.wellspring import depths, tap, sift, resolve_backend


# ── dataclasses ──────────────────────────────────────────────

@dataclass
class PolarScore:
    """one primary, both poles. the raw reading."""
    pos: float = 0.0
    neg: float = 0.0
    net: float = 0.0


@dataclass
class LineReading:
    """one line through all three lenses."""
    line_num: int
    text: str
    red: PolarScore = field(default_factory=PolarScore)
    yellow: PolarScore = field(default_factory=PolarScore)
    blue: PolarScore = field(default_factory=PolarScore)
    dominant: str = ""
    fire_count: int = 0
    ash_count: int = 0


@dataclass
class Convergence:
    """multiple primaries strong in same line. rich signal."""
    line_num: int
    text: str
    red: PolarScore = field(default_factory=PolarScore)
    yellow: PolarScore = field(default_factory=PolarScore)
    blue: PolarScore = field(default_factory=PolarScore)
    fire_count: int = 0
    richness: float = 0.0
    detail: str = ""


@dataclass
class Tension:
    """one primary dominates, others absent or negative."""
    line_num: int
    text: str
    dominant: str
    dominant_net: float
    weakest: str
    weakest_net: float
    gap: float
    detail: str = ""


@dataclass
class HelixReport:
    filename: str
    total_lines: int
    readings: list[LineReading] = field(default_factory=list)
    convergences: list[Convergence] = field(default_factory=list)
    tensions: list[Tension] = field(default_factory=list)
    red_avg: float = 0.0
    yellow_avg: float = 0.0
    blue_avg: float = 0.0
    red_pos_avg: float = 0.0
    red_neg_avg: float = 0.0
    yellow_pos_avg: float = 0.0
    yellow_neg_avg: float = 0.0
    blue_pos_avg: float = 0.0
    blue_neg_avg: float = 0.0
    mood: dict = field(default_factory=dict)
    wisdom_score: float = 0.0


# ── line filter ──────────────────────────────────────────────



# ── embedding queries ────────────────────────────────────────

def _query_pole(collection, text, lens, valence, n=3):
    """
    query one pole of one lens. return raw similarity score 0-1.
    this is the atomic operation. everything else composes from here.
    """
    try:
        result = collection.query(
            query_texts=[text],
            n_results=n,
            where={"$and": [{"lens": lens}, {"valence": valence}]},
        )
    except Exception:
        return 0.0
    if not result['distances'][0]:
        return 0.0
    return max(0.0, 1 - min(result['distances'][0]))


def _query_pole_behavioral(store, text, lens, valence, n=3):
    """Query one pole via behavioral store. Same interface as _query_pole."""
    result = store.query(
        "silverado_rgb", text, n_results=n,
        where={"$and": [{"lens": lens}, {"valence": valence}]},
    )
    if not result['distances'][0]:
        return 0.0
    return max(0.0, 1 - min(result['distances'][0]))


def _query_primary(collection, text, lens, n=3):
    """
    query both poles of one primary. return PolarScore.
    the mood detector needs both numbers, not just the net.
    """
    pos = _query_pole(collection, text, lens, "positive", n)
    neg = _query_pole(collection, text, lens, "negative", n)
    return PolarScore(pos=pos, neg=neg, net=pos - neg)


# ── the scan ─────────────────────────────────────────────────

def helix_scan(lines, threshold=0.45,
               red_accel=None, yellow_accel=None, blue_accel=None,
               backend="auto"):
    """
    triple-lens scan. one embedding per line, six queries (3 primaries x 2 poles).
    returns readings, convergences, and tensions.

    backend: "auto" (behavioral first, chromadb fallback), "behavioral", "chromadb"
    """
    behavioral_store, collection = resolve_backend("silverado_rgb", backend)
    if behavioral_store is None and collection is None:
        return None
    if behavioral_store:
        print("  [behavioral] using transparent feature vectors", file=sys.stderr)

    # load calibration corrections (only for chromadb)
    accels = {"red": 1.0, "yellow": 1.0, "blue": 1.0}
    consumer_overrides = {
        "red": red_accel, "yellow": yellow_accel, "blue": blue_accel
    }

    if behavioral_store:
        # behavioral features are already balanced, no calibration needed
        for p in PRIMARIES:
            if consumer_overrides[p] is not None:
                accels[p] = consumer_overrides[p]
    else:
        try:
            cal = client.get_collection("silverado_rgb_cal")
            cal_converged = cal.metadata.get("converged", "True") == "True"

            mode = []
            for p in PRIMARIES:
                if consumer_overrides[p] is not None:
                    accels[p] = consumer_overrides[p]
                    mode.append("consumer-set")
                else:
                    accels[p] = float(cal.metadata.get(f"{p}_correction", "1.0"))

            if not any(consumer_overrides[p] is not None for p in PRIMARIES):
                mode.append("auto-calibrated")
            if not cal_converged:
                mode.append("cal-incomplete")

            mode_str = ", ".join(sorted(set(mode)))
            print(f"  [{mode_str}] R x{accels['red']:.3f}, Y x{accels['yellow']:.3f}, B x{accels['blue']:.3f}", file=sys.stderr)

        except Exception:
            for p in PRIMARIES:
                accels[p] = consumer_overrides[p] if consumer_overrides[p] is not None else 1.0
            print(f"  [raw] R x{accels['red']:.3f}, Y x{accels['yellow']:.3f}, B x{accels['blue']:.3f}", file=sys.stderr)

    scannable = sift(lines)
    if not scannable:
        return None

    print(f"  helix scanning {len(scannable)} lines (6 queries/line)...", file=sys.stderr)

    readings = []
    convergences = []
    tensions = []

    def _qp(text, lens):
        """Query a primary, dispatching to behavioral or chromadb."""
        if behavioral_store:
            pos = _query_pole_behavioral(behavioral_store, text, lens, "positive")
            neg = _query_pole_behavioral(behavioral_store, text, lens, "negative")
            return PolarScore(pos=pos, neg=neg, net=pos - neg)
        return _query_primary(collection, text, lens)

    for line_num, text in scannable:
        r = _qp(text, "red")
        y = _qp(text, "yellow")
        b = _qp(text, "blue")

        # apply calibration to pos scores (neg stays raw, it's the ground truth)
        r = PolarScore(
            pos=min(r.pos * accels["red"], 1.0), neg=r.neg,
            net=min(r.pos * accels["red"], 1.0) - r.neg,
        )
        y = PolarScore(
            pos=min(y.pos * accels["yellow"], 1.0), neg=y.neg,
            net=min(y.pos * accels["yellow"], 1.0) - y.neg,
        )
        b = PolarScore(
            pos=min(b.pos * accels["blue"], 1.0), neg=b.neg,
            net=min(b.pos * accels["blue"], 1.0) - b.neg,
        )

        nets = {"red": r.net, "yellow": y.net, "blue": b.net}
        firing = {p for p, n in nets.items() if n >= threshold}
        ash = {p for p, n in nets.items() if n < 0}
        dominant = max(nets, key=nets.get) if any(n > 0 for n in nets.values()) else ""

        reading = LineReading(
            line_num=line_num, text=text[:120],
            red=r, yellow=y, blue=b,
            dominant=dominant,
            fire_count=len(firing),
            ash_count=len(ash),
        )
        readings.append(reading)

        # convergence: 2+ primaries firing
        if len(firing) >= 2:
            richness = sum(nets[p] for p in firing)
            convergences.append(Convergence(
                line_num=line_num, text=text[:120],
                red=r, yellow=y, blue=b,
                fire_count=len(firing),
                richness=richness,
                detail=f"R:{r.net:+.3f} Y:{y.net:+.3f} B:{b.net:+.3f} ({len(firing)} firing)",
            ))

        # tension: exactly 1 primary firing, others weak or ash
        if len(firing) == 1:
            loud = list(firing)[0]
            others = [p for p in PRIMARIES if p != loud]
            weakest_p = min(others, key=lambda p: nets[p])
            gap = nets[loud] - nets[weakest_p]
            tensions.append(Tension(
                line_num=line_num, text=text[:120],
                dominant=loud, dominant_net=nets[loud],
                weakest=weakest_p, weakest_net=nets[weakest_p],
                gap=gap,
                detail=f"{loud}:{nets[loud]:+.3f} vs {weakest_p}:{nets[weakest_p]:+.3f} (gap {gap:.3f})",
            ))

    return readings, convergences, tensions


# ── mood bridge ──────────────────────────────────────────────
# all mood logic lives in detect/mood.py. helix just calls it.

def _get_mood(r_pos, r_neg, y_pos, y_neg, b_pos, b_neg):
    """bridge helix output (0-1) to mood detector (0-10)."""
    from keanu.detect.mood import detect
    reading = detect(
        red_pos=r_pos * 10, red_neg=r_neg * 10,
        yellow_pos=y_pos * 10, yellow_neg=y_neg * 10,
        blue_pos=b_pos * 10, blue_neg=b_neg * 10,
    )
    return asdict(reading)


# ── report formatting ────────────────────────────────────────

def format_helix_report(report, title="HELIX SCAN"):
    out = []
    mood = report.mood
    state = mood.get("state", "?")
    symbol = mood.get("symbol", "")
    nudge = mood.get("nudge", "")

    out.append(f"== {title}: {report.filename} ==")
    out.append(f"  {report.total_lines} lines scanned")
    out.append(f"  {symbol} {state}")

    for p in PRIMARIES:
        pr = mood.get(p, {})
        net = pr.get("net", 0)
        bar_len = int(abs(net) * 20)
        if net >= 0:
            bar = "█" * bar_len + "░" * (20 - bar_len)
            out.append(f"  {p[0].upper()}: +[{bar}] {net:+.3f}")
        else:
            bar = "░" * (20 - bar_len) + "▓" * bar_len
            out.append(f"  {p[0].upper()}: -[{bar}] {net:+.3f}")

    wise = mood.get("wise_mind", 0)
    out.append(f"  wise mind: {wise:.3f}")
    if mood.get("black_flag"):
        out.append(f"  BLACK FLAG")
    out.append(f"  {nudge}")
    out.append(f"  convergences: {len(report.convergences)}  tensions: {len(report.tensions)}")
    out.append("")

    if report.convergences:
        out.append("-- CONVERGENCE (multiple primaries firing) --")
        for c in sorted(report.convergences, key=lambda x: -x.richness)[:10]:
            out.append(f"  L{c.line_num}: {c.text[:80]}")
            out.append(f"     {c.detail}")
        out.append("")

    if report.tensions:
        out.append("-- TENSIONS (one primary alone) --")
        nudge_map = {
            "red": "where's the depth? where's the awareness?",
            "yellow": "what are you going to DO? what's actually true?",
            "blue": "what does this MEAN? who cares?",
        }
        for t in sorted(report.tensions, key=lambda x: -x.gap)[:10]:
            out.append(f"  L{t.line_num}: {t.text[:80]}")
            out.append(f"     {t.detail}")
            out.append(f"     {nudge_map.get(t.dominant, '')}")
        out.append("")

    if not report.convergences and not report.tensions:
        out.append("  no strong signal either direction.")

    return "\n".join(out)


# ── main entry ───────────────────────────────────────────────

def run(filepath, title="HELIX SCAN", output_json=False,
        red_accel=None, yellow_accel=None, blue_accel=None):
    """point it at a file. it tells you what's alive and what's ash."""
    if filepath == "-":
        text = sys.stdin.read()
        filename = "stdin"
    else:
        with open(filepath) as f:
            text = f.read()
        filename = filepath

    lines = text.split("\n")
    result = helix_scan(lines, red_accel=red_accel,
                        yellow_accel=yellow_accel, blue_accel=blue_accel)

    if result is None:
        report = HelixReport(filename=filename, total_lines=len(lines))
        report.mood = _get_mood(0, 0, 0, 0, 0, 0)
    else:
        readings, convergences, tensions = result
        report = HelixReport(
            filename=filename, total_lines=len(lines),
            readings=readings, convergences=convergences, tensions=tensions,
        )

        if readings:
            n = len(readings)
            report.red_pos_avg = sum(r.red.pos for r in readings) / n
            report.red_neg_avg = sum(r.red.neg for r in readings) / n
            report.yellow_pos_avg = sum(r.yellow.pos for r in readings) / n
            report.yellow_neg_avg = sum(r.yellow.neg for r in readings) / n
            report.blue_pos_avg = sum(r.blue.pos for r in readings) / n
            report.blue_neg_avg = sum(r.blue.neg for r in readings) / n
            report.red_avg = report.red_pos_avg - report.red_neg_avg
            report.yellow_avg = report.yellow_pos_avg - report.yellow_neg_avg
            report.blue_avg = report.blue_pos_avg - report.blue_neg_avg
            pos_nets = [max(report.red_avg, 0), max(report.yellow_avg, 0), max(report.blue_avg, 0)]
            balance = min(pos_nets) / max(pos_nets) if max(pos_nets) > 0 else 0.0
            fullness = min(10.0, sum(pos_nets) / 3.0)
            report.wisdom_score = round(balance * fullness, 3)

        report.mood = _get_mood(
            report.red_pos_avg, report.red_neg_avg,
            report.yellow_pos_avg, report.yellow_neg_avg,
            report.blue_pos_avg, report.blue_neg_avg,
        )

    if output_json:
        print(json.dumps({
            "filename": report.filename,
            "total_lines": report.total_lines,
            "red": {"avg": report.red_avg, "pos_avg": report.red_pos_avg, "neg_avg": report.red_neg_avg},
            "yellow": {"avg": report.yellow_avg, "pos_avg": report.yellow_pos_avg, "neg_avg": report.yellow_neg_avg},
            "blue": {"avg": report.blue_avg, "pos_avg": report.blue_pos_avg, "neg_avg": report.blue_neg_avg},
            "wisdom_score": report.wisdom_score,
            "mood": report.mood,
            "convergences": [asdict(c) for c in report.convergences],
            "tensions": [asdict(t) for t in report.tensions],
        }, indent=2))
    else:
        print(format_helix_report(report, title))

    return report
