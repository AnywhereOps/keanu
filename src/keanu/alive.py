"""alive.py - text in, ALIVE state out."""

from dataclasses import dataclass, field
from keanu.signal.vibe import AliveState


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
    evidence = []

    r_net = color.get("red_net", 0)
    y_net = color.get("yellow_net", 0)
    b_net = color.get("blue_net", 0)
    cs = color.get("state", "flat")
    balance = color.get("balance", 0)
    fullness = color.get("fullness", 0)
    wise_mind = color.get("wise_mind", 0)

    if cs == "sunrise":
        state = AliveState.GOLD
        evidence.append("sunrise synthesis")

    elif cs in ("black", "dark"):
        state = AliveState.BLACK
        evidence.append(cs)

    elif cs == "flat" and ("withdrawn" in emo_states or not emotions):
        state = AliveState.GREY
        evidence.append("flat" + (" + withdrawn" if "withdrawn" in emo_states else ""))

    elif cs in ("white", "silver"):
        state = AliveState.WHITE
        evidence.append(cs)

    elif cs == "green" or ("energized" in emo_states and balance > 0.5):
        state = AliveState.GREEN
        evidence.append(cs if cs == "green" else "energized + balanced")

    elif cs in ("red+", "red-", "orange") or "frustrated" in emo_states:
        state = AliveState.RED
        evidence.append(cs if cs.startswith("red") else "frustrated")

    elif cs in ("blue+", "blue-") or ("questioning" in emo_states and not _hot(emotions)):
        state = AliveState.BLUE
        evidence.append(cs if cs.startswith("blue") else "questioning")

    elif cs in ("yellow+", "yellow-") or "confused" in emo_states:
        state = AliveState.YELLOW
        evidence.append(cs if cs.startswith("yellow") else "confused")

    elif cs == "purple":
        state = AliveState.RED
        evidence.append("purple: passion + depth")

    elif fullness > 2.0 and balance > 0.4 and not emo_states & {"frustrated", "withdrawn", "isolated", "confused"}:
        state = AliveState.GREEN
        evidence.append("positive, no negatives")

    elif emo_states & {"withdrawn", "isolated"}:
        state = AliveState.GREY
        evidence.append("withdrawn/isolated, weak signal")

    else:
        state = AliveState.YELLOW
        evidence.append("uncertain")

    return AliveReading(
        state=state, emotions=emotions, color_state=cs,
        red_net=r_net, yellow_net=y_net, blue_net=b_net,
        balance=balance, fullness=fullness, wise_mind=wise_mind,
        evidence=evidence,
    )


def _hot(emotions: list) -> bool:
    return any(e.get("intensity", 0) > 0.6 for e in emotions)


def _get_emotions(text: str) -> list:
    from keanu.detect.engine import detect_emotion
    return detect_emotion(text)


def _get_color(text: str) -> dict:
    empty = {"state": "flat", "red_net": 0, "yellow_net": 0, "blue_net": 0,
             "balance": 0, "fullness": 0, "wise_mind": 0}

    from keanu.wellspring import draw
    collection = draw("silverado_rgb")
    if collection is None:
        return empty

    from keanu.scan.helix import _query_primary
    r = _query_primary(collection, text, "red")
    y = _query_primary(collection, text, "yellow")
    b = _query_primary(collection, text, "blue")

    from keanu.detect.mood import detect as mood_detect
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
