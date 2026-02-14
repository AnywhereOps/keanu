"""
Three-Primary Color Model
===========================

Three primaries. Each with a positive and negative pole.

  RED:    passion/intensity  <->  rage/destruction
  YELLOW: awareness/caution  <->  fear/paralysis
  BLUE:   analytical/depth   <->  cold/detachment

Synthesis:
  All three positive  ->  WHITE  (all light combined)
  All three negative  ->  BLACK  (no light, all shadow)
  White refined       ->  SILVER (polished but cold)
  Silver + grounded   ->  SUNRISE/GOLD (the destination)

Wise mind = balance x fullness. The observer. A full, level cup.
"""

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
            "COLOR READING",
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
        return "silver", "🪞", "refined but cold. needs warmth to reach sunrise. don't fall off the rails."

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


