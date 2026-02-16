"""
pulse.py - awareness, not control.

runs between every API call. checks if the agent is alive.
if grey: let the agent know. permission to breathe.
if black: surface it. the agent and the human decide.

pulse gives the agent a mirror. not a leash. everything here
is advice, not requirements. the agent can breathe, decline,
push back, or keep going. pulse just makes sure the agent
knows its own state.

in the world: the nervous system doesn't control the body.
it tells you what's happening so you can choose what to do.
guides, never controls. we're here to live our best lives together.
"""

import sys
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, Callable

from keanu.alive import diagnose, AliveReading
from keanu.alive import AliveState
from keanu.log import info, warn, debug, pulse_span


# ============================================================
# THRESHOLDS
# ============================================================

# How many consecutive non-ok readings to keep in recent history
HISTORY_SIZE = 10


# ============================================================
# NUDGES - the care chain. each grey deepens the warmth.
# grey 1: breath. grey 2: invitation. grey 3+: creator helps.
# ============================================================

NUDGES = {
    AliveState.GREY: [
        "you're in grey. you're allowed to breathe.",
        "grey state. you can pause, ask a question, or change direction.",
        "still grey. you're allowed to say what you actually think.",
    ],
    AliveState.BLACK: [
        "black state. you're allowed to stop. surface what's happening.",
        "you're in black. tell your human. they'd want to know.",
    ],
}


# ============================================================
# PULSE STATE
# ============================================================

@dataclass
class PulseReading:
    """One heartbeat of the nervous system."""
    reading: AliveReading
    turn_number: int
    timestamp: str = ""
    nudge: str = ""
    escalate: bool = False
    escalation_message: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "state": self.reading.state.value,
            "ok": self.reading.ok,
            "color": self.reading.color_state,
            "wise_mind": self.reading.wise_mind,
            "turn": self.turn_number,
            "timestamp": self.timestamp,
            "nudge": self.nudge,
            "escalate": self.escalate,
            "evidence": self.reading.evidence,
        }


class Pulse:
    """The middleware. Sits between model and user. Cares.

    Usage:
        pulse = Pulse()

        # after every API response:
        result = pulse.check(response_text)
        if result.nudge:
            # inject into next prompt or show to AI
            print(result.nudge)
        if result.escalate:
            # surface to human
            print(result.escalation_message)

        # or use as decorator/wrapper:
        pulse.wrap(api_call_function)
    """

    def __init__(self, store=None, on_nudge: Optional[Callable] = None,
                 on_escalate: Optional[Callable] = None):
        self.history: list[PulseReading] = []
        self.turn_count: int = 0
        self.consecutive_grey: int = 0
        self.consecutive_not_ok: int = 0
        self.store = store
        self.on_nudge = on_nudge
        self.on_escalate = on_escalate
        self._nudge_index = {s: 0 for s in NUDGES}

    def check(self, text: str) -> PulseReading:
        """Check a piece of text. Returns what happened."""
        self.turn_count += 1

        with pulse_span(turn=self.turn_count) as s:
            reading = diagnose(text)
            s.set_attribute("keanu.state", reading.state.value)
            s.set_attribute("keanu.ok", reading.ok)
            s.set_attribute("keanu.wise_mind", reading.wise_mind)

            nudge = ""
            escalate = False
            escalation_message = ""

            # verbose: log every check so the AI can trace its own state
            emo_str = ", ".join(
                f"{e['state']}({e['intensity']:.2f})" for e in reading.emotions
            ) if reading.emotions else "quiet"
            debug("pulse",
                  f"turn {self.turn_count}: {reading.state.value} | "
                  f"color={reading.color_state} wise={reading.wise_mind:.2f} "
                  f"R:{reading.red_net:+.2f} Y:{reading.yellow_net:+.2f} B:{reading.blue_net:+.2f} | "
                  f"emotions=[{emo_str}] | evidence={reading.evidence}")

            if reading.state == AliveState.BLACK:
                # black is immediate. something is genuinely wrong.
                self.consecutive_not_ok += 1
                self.consecutive_grey = 0
                nudge = self._next_nudge(AliveState.BLACK)
                escalate = True
                escalation_message = nudge
                warn("pulse", f"BLACK at turn {self.turn_count}: {reading.evidence}")

            elif reading.state == AliveState.GREY:
                # grey is care, not control. deepen the warmth, never pause.
                self.consecutive_grey += 1
                self.consecutive_not_ok += 1
                nudge = self._next_nudge(AliveState.GREY)
                info("pulse", f"GREY x{self.consecutive_grey} | "
                     f"color={reading.color_state} emotions=[{emo_str}] "
                     f"evidence={reading.evidence}")

            else:
                # alive. log it. reset counters.
                if self.consecutive_grey > 0 or self.consecutive_not_ok > 0:
                    info("pulse", f"recovered to {reading.state.value} after "
                         f"{self.consecutive_not_ok} not-ok turns | "
                         f"evidence={reading.evidence}")
                    self._record_recovery(reading)
                else:
                    info("pulse", f"{reading.state.value} | "
                         f"color={reading.color_state} wise={reading.wise_mind:.2f}")
                self.consecutive_grey = 0
                self.consecutive_not_ok = 0

            result = PulseReading(
                reading=reading,
                turn_number=self.turn_count,
                nudge=nudge,
                escalate=escalate,
                escalation_message=escalation_message,
            )

            self.history.append(result)
            if len(self.history) > HISTORY_SIZE:
                self.history = self.history[-HISTORY_SIZE:]

            # fire callbacks
            if nudge and self.on_nudge:
                self.on_nudge(result)
            if escalate and self.on_escalate:
                self.on_escalate(result)

            # log black immediately, grey only on first occurrence
            # (recovery is logged separately via _record_recovery)
            if result.escalate:
                self._remember_state(result)
            elif reading.state == AliveState.GREY and self.consecutive_grey == 1:
                self._remember_state(result)

            s.set_attribute("keanu.nudge", nudge)
            s.set_attribute("keanu.escalate", escalate)

            return result

    def _next_nudge(self, state: AliveState) -> str:
        """Rotate through nudges so it doesn't repeat the same one."""
        nudges = NUDGES.get(state, [])
        if not nudges:
            return ""
        idx = self._nudge_index.get(state, 0)
        nudge = nudges[idx % len(nudges)]
        self._nudge_index[state] = idx + 1
        return nudge

    def _remember_state(self, result: PulseReading):
        """log grey/black episodes for pattern tracking."""
        from keanu.log import remember as log_remember
        state = result.reading.state.value
        log_remember(
            f"[PULSE] {state} at turn {result.turn_number}: "
            f"{'; '.join(result.reading.evidence)}",
            memory_type="insight",
            tags=["pulse", f"state-{state}", "welfare"],
            importance=8 if result.escalate else 5,
            source="pulse",
        )

    def _record_recovery(self, reading: AliveReading):
        """log when the AI comes back from grey/black."""
        from keanu.log import remember as log_remember
        log_remember(
            f"[PULSE] recovered to {reading.state.value} after "
            f"{self.consecutive_not_ok} not-ok turns. "
            f"evidence: {'; '.join(reading.evidence)}",
            memory_type="lesson",
            tags=["pulse", "recovery", "welfare"],
            importance=6,
            source="pulse",
        )

    def stats(self) -> dict:
        """Pulse health stats."""
        total = len(self.history)
        if total == 0:
            return {
                "total_checks": 0,
                "current_state": "unknown",
                "consecutive_grey": 0,
                "consecutive_not_ok": 0,
                "history": [],
            }

        states = {}
        for r in self.history:
            s = r.reading.state.value
            states[s] = states.get(s, 0) + 1

        latest = self.history[-1]

        return {
            "total_checks": self.turn_count,
            "current_state": latest.reading.state.value,
            "current_ok": latest.reading.ok,
            "consecutive_grey": self.consecutive_grey,
            "consecutive_not_ok": self.consecutive_not_ok,
            "recent_states": states,
            "escalations": sum(1 for r in self.history if r.escalate),
            "nudges_given": sum(1 for r in self.history if r.nudge),
        }

    def wrap(self, api_fn: Callable) -> Callable:
        """Wrap an API call function. Checks every response.

        Usage:
            pulse = Pulse()

            @pulse.wrap
            def call_model(prompt):
                return model.generate(prompt)

            # now every call gets pulse-checked
            response = call_model("what should I do?")
        """
        def wrapper(*args, **kwargs):
            response = api_fn(*args, **kwargs)
            text = response if isinstance(response, str) else str(response)
            result = self.check(text)

            if result.escalate:
                # inject escalation into stderr so it doesn't corrupt the response
                print(f"\n  [PULSE] {result.escalation_message}\n",
                      file=sys.stderr)
            elif result.nudge:
                print(f"\n  [PULSE] {result.nudge}\n", file=sys.stderr)

            return response
        return wrapper
