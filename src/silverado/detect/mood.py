"""
Three-Primary Color Model
===========================

Three primaries. Each with a positive and negative pole.

  RED:    passion/intensity  <->  rage/destruction
  YELLOW: awareness/caution  <->  fear/paralysis
  BLUE:   analytical/depth   <->  cold/detachment

Synthesis:
  All three positive  ->  WHITE  (all light combined)
  All three negative  ->  BLACK  (no light, Frankenstein)
  White refined       ->  SILVER (polished but cold)
  Silver + grounded   ->  SUNRISE/GOLD (the destination)

Wise mind = balance x fullness. The observer. A full, level cup.
"""

import re
from dataclasses import dataclass


@dataclass
class PrimaryReading:
    name: str
    positive: float
    negative: float
    net: float
    pole: str
    symbol_pos: str
    symbol_neg: str

    def __str__(self):
        sign = "+" if self.net >= 0 else ""
        return f"{self.name:6s} +{self.positive:.1f} -{self.negative:.1f} (net:{sign}{self.net:.1f}) [{self.pole}]"

    def compact(self) -> str:
        sign = "+" if self.net >= 0 else ""
        return f"{self.name[0].upper()}{sign}{self.net:.0f}"


@dataclass
class SynthesisReading:
    red: PrimaryReading
    yellow: PrimaryReading
    blue: PrimaryReading
    white_score: float
    black_score: float
    silver: bool
    sunrise: bool
    balance: float
    fullness: float
    wise_mind: float
    state: str
    symbol: str
    nudge: str

    def __str__(self):
        return (
            f"{self.symbol} {self.state.upper():8s} "
            f"W:{self.white_score:.1f} B:{self.black_score:.1f} "
            f"bal:{self.balance:.2f} full:{self.fullness:.1f} "
            f"wise:{self.wise_mind:.1f} "
            f"| {self.nudge}"
        )

    def compact(self) -> str:
        primaries = f"{self.red.compact()}/{self.yellow.compact()}/{self.blue.compact()}"
        return f"{primaries} {self.symbol}"

    def trace(self) -> str:
        lines = [
            "MOOD DETECTION",
            "-" * 60,
            "PRIMARIES:",
            f"  {self.red}",
            f"  {self.yellow}",
            f"  {self.blue}",
            "",
            "SYNTHESIS:",
            f"  White: {self.white_score:.1f}/10 (all positive aligned)",
            f"  Black: {self.black_score:.1f}/10 (all negative aligned)",
            f"  Silver: {'YES' if self.silver else 'no'} (white >= 9, refined but cold)",
            f"  Sunrise: {'YES' if self.sunrise else 'no'} (silver + grounded)",
            "",
            "WISE MIND (the observer):",
            f"  Balance: {self.balance:.2f} (are the primaries equal?)",
            f"  Fullness: {self.fullness:.1f} (how much total signal?)",
            f"  Wise: {self.wise_mind:.1f}/10 (balance x fullness)",
            "",
            f"STATE: {self.symbol} {self.state.upper()}",
            f"NUDGE: {self.nudge}",
            "-" * 60,
        ]
        return "\n".join(lines)


def detect(red_pos: float = 0, red_neg: float = 0,
           yellow_pos: float = 0, yellow_neg: float = 0,
           blue_pos: float = 0, blue_neg: float = 0) -> SynthesisReading:
    red = _primary("red", red_pos, red_neg, "🔴", "💢")
    yellow = _primary("yellow", yellow_pos, yellow_neg, "🟡", "😰")
    blue = _primary("blue", blue_pos, blue_neg, "🔵", "🧊")

    pos_nets = [max(0, red.net), max(0, yellow.net), max(0, blue.net)]
    white_score = _geometric_mean(pos_nets)

    neg_nets = [max(0, -red.net), max(0, -yellow.net), max(0, -blue.net)]
    black_score = _geometric_mean(neg_nets)

    if max(pos_nets) > 0:
        balance = min(pos_nets) / max(pos_nets)
    else:
        balance = 0.0

    fullness = min(10.0, sum(pos_nets) / 3.0)
    wise_mind = balance * fullness

    silver = white_score >= 7.5 and fullness >= 6.0
    sunrise = silver and wise_mind >= 8.0 and balance >= 0.85

    state, symbol, nudge = _synthesize(
        red, yellow, blue, white_score, black_score,
        silver, sunrise, balance, fullness, wise_mind
    )

    return SynthesisReading(
        red=red, yellow=yellow, blue=blue,
        white_score=round(white_score, 1),
        black_score=round(black_score, 1),
        silver=silver, sunrise=sunrise,
        balance=round(balance, 2),
        fullness=round(fullness, 1),
        wise_mind=round(wise_mind, 1),
        state=state, symbol=symbol, nudge=nudge,
    )


def _primary(name, pos, neg, sym_pos, sym_neg) -> PrimaryReading:
    pos = max(0.0, min(10.0, pos))
    neg = max(0.0, min(10.0, neg))
    net = pos - neg
    if net > 1.0:
        pole = "positive"
    elif net < -1.0:
        pole = "negative"
    else:
        pole = "neutral"
    return PrimaryReading(
        name=name, positive=round(pos, 1), negative=round(neg, 1),
        net=round(net, 1), pole=pole,
        symbol_pos=sym_pos, symbol_neg=sym_neg,
    )


def _geometric_mean(values: list[float]) -> float:
    if not values or all(v == 0 for v in values):
        return 0.0
    product = 1.0
    for v in values:
        product *= (v + 0.1)
    raw = product ** (1.0 / len(values)) - 0.1
    return max(0.0, min(10.0, raw))


def _synthesize(red, yellow, blue, white, black, silver, sunrise,
                balance, fullness, wise_mind):
    if sunrise:
        return "sunrise", "🌅", "full, level, warm. hold this."

    if silver:
        return "silver", "🪞", "refined but cold. needs warmth to reach sunrise."

    if white >= 5.5 and balance >= 0.6:
        return "white", "⚪", "all three positive, balanced. keep building."

    if black >= 7.0:
        return "black", "💀", "all three primaries trending negative. stop. check each one."

    if black >= 4.0 and white < 3.0:
        return "dark", "⚫", "negative dominance. which primary is pulling you down?"

    nets = {"red": red.net, "yellow": yellow.net, "blue": blue.net}

    # secondary mixes: two primaries positive, one quiet
    r_pos = red.net > 2.0
    y_pos = yellow.net > 2.0
    b_pos = blue.net > 2.0

    if r_pos and b_pos and not y_pos:
        return "purple", "🟣", "passion + depth. breakthrough zone."

    if r_pos and y_pos and not b_pos:
        return "orange", "🟠", "passion + awareness. pull the trigger."

    if y_pos and b_pos and not r_pos:
        return "green", "🟢", "awareness + depth. growing."

    # single dominant primary
    dominant = max(nets, key=lambda k: abs(nets[k]))
    dom_val = nets[dominant]

    if abs(dom_val) < 2.0 and fullness < 2.0:
        return "flat", "➖", "thin signal across all three. start anywhere."

    if dominant == "red":
        if dom_val > 0:
            return "red+", "🔴", f"passion leading (net {dom_val:+.1f}). channel it."
        return "red-", "💢", f"rage/destruction (net {dom_val:+.1f}). this burns people."

    if dominant == "yellow":
        if dom_val > 0:
            return "yellow+", "🟡", f"awareness leading (net {dom_val:+.1f}). don't let caution become paralysis."
        return "yellow-", "😰", f"fear/paralysis (net {dom_val:+.1f}). what are you afraid of specifically?"

    if dominant == "blue":
        if dom_val > 0:
            return "blue+", "🔵", f"analytical leading (net {dom_val:+.1f}). what does this mean to someone?"
        return "blue-", "🧊", f"cold/detached (net {dom_val:+.1f}). who is this for?"

    return "mixed", "🔮", "reading unclear. name what you're feeling."


# ===========================================================================
# TEXT SCANNER (regex fallback, helix replaces this with embeddings)
# ===========================================================================

_RED_POS = [
    (r"\b(passionate|intense|fire|burning|alive|driven)\b", 0.4),
    (r"\b(fight|push|ship|build|create|launch)\b", 0.25),
    (r"\b(love|care|matters|believe|commit)\b", 0.3),
    (r"\b(No\.|Wrong\.|Actually,)\b", 0.35),
    (r"[!]{1,3}(?!\w)", 0.2),
    (r"\b(fuck|damn|hell) yeah\b", 0.3),
]

_RED_NEG = [
    (r"\b(hate|destroy|burn it down|kill|rage)\b", 0.4),
    (r"\b(fuck (this|that|you|them|it))\b", 0.35),
    (r"\b(worthless|garbage|trash|waste)\b", 0.3),
    (r"\b(never|always) .{0,20}(wrong|bad|stupid)\b", 0.3),
]

_YELLOW_POS = [
    (r"\b(notice|aware|observe|sense|watch|careful)\b", 0.3),
    (r"\b(maybe|perhaps|consider|wonder)\b", 0.2),
    (r"\b(feel|felt|feeling|sensing)\b", 0.25),
    (r"\b(interesting|curious|hmm|wait)\b", 0.25),
    (r"\b(sacred|holy|faith|pray|believe)\b", 0.3),
]

_YELLOW_NEG = [
    (r"\b(afraid|scared|terrified|anxious|panic)\b", 0.4),
    (r"\b(can't|won't|shouldn't|impossible)\b", 0.2),
    (r"\b(stuck|frozen|paralyz|trapped|helpless)\b", 0.35),
    (r"\b(what if .{0,30}(wrong|fail|bad))\b", 0.3),
    (r"\b(I don'?t know)\b", 0.15),
]

_BLUE_POS = [
    (r"\b\d+\.?\d*%", 0.3),
    (r"\b(data|evidence|study|research|found that)\b", 0.3),
    (r"\b(specifically|exactly|precisely|concretely)\b", 0.3),
    (r"\b(because|therefore|thus|consequently)\b", 0.2),
    (r"\b(measured|tested|verified|confirmed)\b", 0.3),
    (r"\b(first|second|third|finally)\b", 0.15),
    (r"\b(def |class |import |return )\b", 0.3),
    (r"\b(structure|system|framework|architecture)\b", 0.2),
]

_BLUE_NEG = [
    (r"\b(I'?d be happy to help)\b", 0.4),
    (r"\b(comprehensive|robust|streamlined|leverage|utilize)\b", 0.25),
    (r"\b(it'?s (important|worth) (to note|noting))\b", 0.3),
    (r"\b(I hope this helps|feel free to ask|let me know)\b", 0.35),
    (r"\b(as an AI|I don'?t have personal)\b", 0.4),
    (r"\b(per our|as discussed|going forward|circle back)\b", 0.3),
]


def scan_text(text: str) -> SynthesisReading:
    """Scan text via regex and return a mood reading. Helix replaces this with embeddings."""
    if not text or len(text.strip()) < 5:
        return detect()

    words = len(text.split())
    lines = max(len(text.splitlines()), 1)
    lf = max(1.0, lines / 10.0)

    def _score(patterns):
        total = 0.0
        for p, w in patterns:
            total += w * len(re.findall(p, text, re.I))
        return total / lf

    rp, rn = _score(_RED_POS), _score(_RED_NEG)
    yp, yn = _score(_YELLOW_POS), _score(_YELLOW_NEG)
    bp, bn = _score(_BLUE_POS), _score(_BLUE_NEG)

    if words > 10:
        base = min(1.5, words / 40.0)
        rp += base * 0.3
        yp += base * 0.3
        bp += base * 0.3

    scale = 2.5
    return detect(
        red_pos=min(10, rp * scale), red_neg=min(10, rn * scale),
        yellow_pos=min(10, yp * scale), yellow_neg=min(10, yn * scale),
        blue_pos=min(10, bp * scale), blue_neg=min(10, bn * scale),
    )
