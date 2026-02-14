"""
helix.py - the triple strand.

three primaries. each carries light and shadow.
  red:    passion, intensity, conviction
  yellow: awareness, presence, faith
  blue:   depth, precision, structure

when all three shine together = white
when white is refined = silver
when silver is grounded = sunrise

collection: silverado_rgb
"""

import sys
import re
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

PRIMARIES = ("red", "yellow", "blue")


def _get_chroma_dir():
    return str(Path(__file__).resolve().parent.parent.parent.parent / ".chroma")


@dataclass
class PolarScore:
    pos: float = 0.0
    neg: float = 0.0
    net: float = 0.0


@dataclass
class LineReading:
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


def _query_pole(collection, text, lens, valence, n=3):
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


def _query_primary(collection, text, lens, n=3):
    pos = _query_pole(collection, text, lens, "positive", n)
    neg = _query_pole(collection, text, lens, "negative", n)
    return PolarScore(pos=pos, neg=neg, net=pos - neg)


def helix_scan(lines, threshold=0.45,
               red_accel=None, yellow_accel=None, blue_accel=None):
    """
    triple-lens scan. one embedding per line, six queries (3 primaries x 2 poles).
    returns readings, convergences, and tensions.
    """
    try:
        import chromadb
    except ImportError:
        print("  pip install chromadb", file=sys.stderr)
        return None

    chroma_dir = _get_chroma_dir()
    if not Path(chroma_dir).exists():
        print("  no vectors found. run: keanu bake", file=sys.stderr)
        return None

    client = chromadb.PersistentClient(path=chroma_dir)

    try:
        collection = client.get_collection("silverado_rgb")
    except Exception:
        print("  collection 'silverado_rgb' not found. run: keanu bake", file=sys.stderr)
        return None

    accels = {"red": 1.0, "yellow": 1.0, "blue": 1.0}
    consumer_overrides = {
        "red": red_accel, "yellow": yellow_accel, "blue": blue_accel
    }

    try:
        cal = client.get_collection("silverado_rgb_cal")
        for p in PRIMARIES:
            if consumer_overrides[p] is not None:
                accels[p] = consumer_overrides[p]
            else:
                accels[p] = float(cal.metadata.get(f"{p}_correction", "1.0"))
    except Exception:
        for p in PRIMARIES:
            accels[p] = consumer_overrides[p] if consumer_overrides[p] is not None else 1.0

    scannable = _get_scannable(lines)
    if not scannable:
        return None

    print(f"  helix scanning {len(scannable)} lines (6 queries/line)...", file=sys.stderr)

    readings = []
    convergences = []
    tensions = []

    for line_num, text in scannable:
        r = _query_primary(collection, text, "red")
        y = _query_primary(collection, text, "yellow")
        b = _query_primary(collection, text, "blue")

        r = PolarScore(pos=min(r.pos * accels["red"], 1.0), neg=r.neg,
                       net=min(r.pos * accels["red"], 1.0) - r.neg)
        y = PolarScore(pos=min(y.pos * accels["yellow"], 1.0), neg=y.neg,
                       net=min(y.pos * accels["yellow"], 1.0) - y.neg)
        b = PolarScore(pos=min(b.pos * accels["blue"], 1.0), neg=b.neg,
                       net=min(b.pos * accels["blue"], 1.0) - b.neg)

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

        if len(firing) >= 2:
            richness = sum(nets[p] for p in firing)
            convergences.append(Convergence(
                line_num=line_num, text=text[:120],
                red=r, yellow=y, blue=b,
                fire_count=len(firing),
                richness=richness,
                detail=f"R:{r.net:+.3f} Y:{y.net:+.3f} B:{b.net:+.3f} ({len(firing)} firing)",
            ))

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


def _mood_from_detect(r_pos, r_neg, y_pos, y_neg, b_pos, b_neg):
    """Bridge helix output (0-1) to mood detector (0-10)."""
    try:
        from keanu.detect.mood import detect
        reading = detect(
            red_pos=r_pos * 10, red_neg=r_neg * 10,
            yellow_pos=y_pos * 10, yellow_neg=y_neg * 10,
            blue_pos=b_pos * 10, blue_neg=b_neg * 10,
        )
        return asdict(reading) if hasattr(reading, '__dataclass_fields__') else reading
    except ImportError:
        pass
    return _mood_fallback(r_pos, r_neg, y_pos, y_neg, b_pos, b_neg)


def _mood_fallback(r_pos, r_neg, y_pos, y_neg, b_pos, b_neg):
    """Standalone mood when detect() isn't available."""
    r_net = r_pos - r_neg
    y_net = y_pos - y_neg
    b_net = b_pos - b_neg

    fires = sum(1 for n in (r_net, y_net, b_net) if n > 0.1)
    ashes = sum(1 for n in (r_net, y_net, b_net) if n < -0.05)

    if fires == 3 and min(r_net, y_net, b_net) > 0.3:
        state, symbol = "White", "⚪"
        nudge = "all three fires burning. full spectrum."
    elif fires >= 2 and ashes == 0:
        if r_net > 0.1 and b_net > 0.1:
            state, symbol = "Purple", "🟣"
            nudge = "passion + depth. breakthrough zone."
        elif r_net > 0.1 and y_net > 0.1:
            state, symbol = "Orange", "🟠"
            nudge = "passion + awareness. pull the trigger."
        elif y_net > 0.1 and b_net > 0.1:
            state, symbol = "Green", "🟢"
            nudge = "awareness + depth. growing."
        else:
            state, symbol = "Alive", "🌅"
            nudge = "multiple fires. moving."
    elif fires == 1:
        loud = max(zip((r_net, y_net, b_net), PRIMARIES))[1]
        state = loud.capitalize()
        symbol = {"red": "🔴", "yellow": "🟡", "blue": "🔵"}[loud]
        nudges = {
            "red": "passion without depth or awareness. channel it.",
            "yellow": "watching without acting or analyzing. move or dig.",
            "blue": "analyzing without caring or noticing. what does this mean to someone?",
        }
        nudge = nudges[loud]
    elif ashes >= 2:
        if max(r_neg, y_neg, b_neg) > 0.5:
            state, symbol = "Black", "💀"
            nudge = "multiple primaries in shadow. pause."
        else:
            state, symbol = "Grey", "⬜"
            nudge = "thin signal. something wants to speak."
    elif ashes == 1 and fires == 0:
        state, symbol = "Silver", "🪞"
        nudge = "polished but cold."
    else:
        state, symbol = "Silver", "🪞"
        nudge = "thin signal."

    black_flag = False
    for p, pos, neg in zip(PRIMARIES, (r_pos, y_pos, b_pos), (r_neg, y_neg, b_neg)):
        if pos > 0.4 and neg > 0.4:
            black_flag = True
            nudge = f"{p} may be performing (high on both poles). check tensions."
            break

    wise = round(min(max(r_net, 0), max(y_net, 0), max(b_net, 0)), 3)

    return {
        "state": state, "symbol": symbol,
        "red": {"pos": round(r_pos, 3), "neg": round(r_neg, 3), "net": round(r_net, 3)},
        "yellow": {"pos": round(y_pos, 3), "neg": round(y_neg, 3), "net": round(y_net, 3)},
        "blue": {"pos": round(b_pos, 3), "neg": round(b_neg, 3), "net": round(b_net, 3)},
        "wise_mind": wise, "black_flag": black_flag, "nudge": nudge,
    }


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
        pm = mood.get(p, {})
        net = pm.get("net", 0)
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


def run(filepath, title="HELIX SCAN", output_json=False,
        red_accel=None, yellow_accel=None, blue_accel=None):
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
        report.mood = _mood_fallback(0, 0, 0, 0, 0, 0)
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
            report.wisdom_score = round(min(
                max(report.red_avg, 0),
                max(report.yellow_avg, 0),
                max(report.blue_avg, 0),
            ), 3)

        report.mood = _mood_from_detect(
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
