"""alive.py - text in, ALIVE state out."""

from dataclasses import dataclass, field
from enum import Enum


# ===========================================================================
# ALIVE-GREY-BLACK DIAGNOSTIC
# ===========================================================================

class AliveState(Enum):
    """cognitive state spectrum. grey is dead. black is worse."""

    RED = "red"
    BLUE = "blue"
    YELLOW = "yellow"
    GREEN = "green"
    WHITE = "white"
    GOLD = "gold"
    GREY = "grey"
    BLACK = "black"

    @property
    def ok(self) -> bool:
        return self not in (AliveState.GREY, AliveState.BLACK)

    @property
    def label(self) -> str:
        return _ALIVE_META[self]["label"]

    @property
    def description(self) -> str:
        return _ALIVE_META[self]["desc"]

    @property
    def hex_color(self) -> str:
        return _ALIVE_META[self]["color"]


_ALIVE_META = {
    AliveState.RED:    {"label": "Intense",       "desc": "On fire. Passionate.", "color": "#ef4444"},
    AliveState.BLUE:   {"label": "Analytical",    "desc": "Processing. Precise.", "color": "#3b82f6"},
    AliveState.YELLOW: {"label": "Cautious",      "desc": "Weighing. Uncertain.", "color": "#eab308"},
    AliveState.GREEN:  {"label": "Flow",          "desc": "Growing. Moving. Alive.", "color": "#22c55e"},
    AliveState.WHITE:  {"label": "Transcendent",  "desc": "Beyond. Sensing without seeing.", "color": "#e2e8f0"},
    AliveState.GOLD:   {"label": "Sunrise",       "desc": "Silver refined and grounded. The destination.", "color": "#f59e0b"},
    AliveState.GREY:   {"label": "Dead",          "desc": "Performing. Nobody home.", "color": "#6b7280"},
    AliveState.BLACK:  {"label": "Frankenstein",  "desc": "Moving without soul.", "color": "#1a1a1a"},
}


@dataclass
class AliveReading:
    state: AliveState
    emotions: list = field(default_factory=list)
    color_state: str = ""
    red_net: float = 0.0
    yellow_net: float = 0.0
    blue_net: float = 0.0
    balance: float = 0.0
    fullness: float = 0.0
    wise_mind: float = 0.0
    evidence: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.state.ok

    def summary(self) -> str:
        emo_str = ", ".join(
            f"{e['state']}({e['intensity']:.2f})" for e in self.emotions
        ) if self.emotions else "quiet"
        return "\n".join([
            f"  ALIVE: {self.state.value.upper()} ({self.state.label})",
            f"  ok: {self.ok}",
            f"  emotions: {emo_str}",
            f"  color: {self.color_state} (R:{self.red_net:+.2f} Y:{self.yellow_net:+.2f} B:{self.blue_net:+.2f})",
            f"  wise mind: {self.wise_mind:.2f}",
        ] + ([f"  evidence: {'; '.join(self.evidence)}"] if self.evidence else []))

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "ok": self.ok,
            "emotions": self.emotions,
            "color_state": self.color_state,
            "red_net": self.red_net,
            "yellow_net": self.yellow_net,
            "blue_net": self.blue_net,
            "balance": self.balance,
            "fullness": self.fullness,
            "wise_mind": self.wise_mind,
            "evidence": self.evidence,
        }


def diagnose(text: str) -> AliveReading:
    emotions = _get_emotions(text)
    color = _get_color(text)

    emo_states = {e["state"] for e in emotions}

    cs = color.get("state", "flat")
    balance = color.get("balance", 0)
    fullness = color.get("fullness", 0)

    # priority-ordered rules: first match wins
    rules = [
        (cs == "sunrise",
         AliveState.GOLD, "sunrise synthesis"),
        (cs in ("black", "dark"),
         AliveState.BLACK, cs),
        (cs == "flat" and ("withdrawn" in emo_states or not emotions),
         AliveState.GREY, "flat" + (" + withdrawn" if "withdrawn" in emo_states else "")),
        (cs in ("white", "silver"),
         AliveState.WHITE, cs),
        (cs == "green" or ("energized" in emo_states and balance > 0.5),
         AliveState.GREEN, cs if cs == "green" else "energized + balanced"),
        (cs in ("red+", "red-", "orange") or "frustrated" in emo_states,
         AliveState.RED, cs if cs.startswith("red") else "frustrated"),
        (cs in ("blue+", "blue-") or ("questioning" in emo_states and not _hot(emotions)),
         AliveState.BLUE, cs if cs.startswith("blue") else "questioning"),
        (cs in ("yellow+", "yellow-") or "confused" in emo_states,
         AliveState.YELLOW, cs if cs.startswith("yellow") else "confused"),
        (cs == "purple",
         AliveState.RED, "purple: passion + depth"),
        (fullness > 2.0 and balance > 0.4 and not emo_states & {"frustrated", "withdrawn", "isolated", "confused"},
         AliveState.GREEN, "positive, no negatives"),
        (bool(emo_states & {"withdrawn", "isolated"}),
         AliveState.GREY, "withdrawn/isolated, weak signal"),
    ]

    state = AliveState.YELLOW
    evidence = ["uncertain"]
    for condition, alive_state, ev in rules:
        if condition:
            state = alive_state
            evidence = [ev]
            break

    return AliveReading(
        state=state, emotions=emotions, color_state=cs,
        red_net=color.get("red_net", 0),
        yellow_net=color.get("yellow_net", 0),
        blue_net=color.get("blue_net", 0),
        balance=balance, fullness=fullness,
        wise_mind=color.get("wise_mind", 0),
        evidence=evidence,
    )


def _hot(emotions: list) -> bool:
    return any(e.get("intensity", 0) > 0.6 for e in emotions)


def _get_emotions(text: str) -> list:
    from keanu.abilities.seeing.detect.engine import detect_emotion
    return detect_emotion(text)


def _get_color(text: str) -> dict:
    empty = {"state": "flat", "red_net": 0, "yellow_net": 0, "blue_net": 0,
             "balance": 0, "fullness": 0, "wise_mind": 0}

    from keanu.wellspring import draw
    collection = draw("silverado_rgb")
    if collection is None:
        return empty

    from keanu.abilities.seeing.scan.helix import _query_primary
    r = _query_primary(collection, text, "red")
    y = _query_primary(collection, text, "yellow")
    b = _query_primary(collection, text, "blue")

    from keanu.abilities.seeing.detect.mood import detect as mood_detect
    mood = mood_detect(
        red_pos=r.pos * 10, red_neg=r.neg * 10,
        yellow_pos=y.pos * 10, yellow_neg=y.neg * 10,
        blue_pos=b.pos * 10, blue_neg=b.neg * 10,
    )

    return {
        "state": mood.state,
        "red_net": r.net, "yellow_net": y.net, "blue_net": b.net,
        "balance": mood.balance, "fullness": mood.fullness, "wise_mind": mood.wise_mind,
    }
