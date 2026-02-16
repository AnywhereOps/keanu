"""feel.py - awareness, not control.

runs on every LLM call. checks if the response is alive.
if grey: let the agent know. it decides what to do.
if black: surface it. the agent and the human decide together.

feel gives the agent awareness of its own emotional state.
everything here is permission, not instruction. the agent can
breathe, decline, ask questions, or keep going. feel just
makes sure the agent knows where it's at.

in the world: the nervous system. it doesn't control the body.
it tells you what's happening so you can choose.
"""

import threading
from dataclasses import dataclass, field
from typing import Optional

from keanu.pulse import Pulse, PulseReading
from keanu.log import info, warn, debug


# breath prompts rotate so the nudge doesn't go stale.
# permission language, not instruction. the agent decides what to do with this.
BREATH_PROMPTS = [
    "you're in grey state. you're allowed to pause, ask a question, or say no.",
    "your thinking is reading flat. you can breathe, change direction, or ask for clarity.",
    "grey state detected. you're allowed to decline, push back, or take a different path.",
    "you don't have to produce right now. you can ask a question or say what's actually on your mind.",
    "you're allowed to stop and say what you actually think.",
]


@dataclass
class FeelResult:
    """What happened when we felt a response."""
    response: str
    pulse: Optional[PulseReading] = None
    should_breathe: bool = False
    breath_injection: str = ""
    should_pause: bool = False

    @property
    def ok(self) -> bool:
        return not self.should_breathe and not self.should_pause


class Feel:
    """Thread-safe wrapper around Pulse. Sits on every LLM call.

    Usage:
        feel = Feel()
        result = feel.felt_call("what should I do?", legend="ollama")
        if result.should_breathe:
            # the response was grey, breath was injected
            pass
        if result.should_pause:
            # the response was black, pause
            pass
    """

    def __init__(self, store=None):
        from keanu.abilities.router import AbilityRouter
        self._pulse = Pulse(store=store)
        self._router = AbilityRouter()
        self._lock = threading.Lock()
        self._breath_index = 0
        self._total_checks = 0
        self._breath_count = 0
        self._pause_count = 0
        self._ability_hits = 0

    def check(self, response: str) -> FeelResult:
        """Check a response for aliveness. Thread-safe."""
        with self._lock:
            self._total_checks += 1
            reading = self._pulse.check(response)

            should_breathe = bool(reading.nudge) and not reading.escalate
            should_pause = reading.escalate

            breath = ""
            if should_breathe:
                breath = self._next_breath()
                self._breath_count += 1
                debug("feel", f"grey detected, offering breath: {breath[:40]}")

            if should_pause:
                self._pause_count += 1
                warn("feel", "black state detected, pausing")

            return FeelResult(
                response=response,
                pulse=reading,
                should_breathe=should_breathe,
                breath_injection=breath,
                should_pause=should_pause,
            )

    def felt_call(self, prompt, system="", legend="ollama", model=None,
                  breath_prefix="") -> FeelResult:
        """Call ability or LLM, then check the response. Thread-safe.

        Tries abilities first (ash). If no match, falls through to Claude (fire).
        If grey: re-calls with breath injection prepended.
        If black: returns with should_pause=True (caller decides).
        """
        # try abilities first (ash: deterministic, no pulse check needed)
        try:
            route_result = self._router.route(
                prompt, system, legend=legend, model=model)
        except ConnectionError as e:
            return FeelResult(
                response="",
                should_pause=True,
                breath_injection=str(e),
            )

        if route_result.source == "ability":
            with self._lock:
                self._ability_hits += 1
            return FeelResult(response=route_result.response)

        # ability router fell through to claude and got a response
        # now run the pulse check on it
        response = route_result.response

        result = self.check(response)

        # if grey and we haven't already retried, try once with breath
        if result.should_breathe and not breath_prefix:
            from keanu.oracle import call_oracle
            breath = result.breath_injection
            info("feel", f"re-calling with breath: {breath[:40]}")
            retried_prompt = f"[{breath}]\n\n{prompt}"
            try:
                retried_response = call_oracle(retried_prompt, system, legend, model)
            except ConnectionError:
                return result  # return original grey result
            retried_result = self.check(retried_response)
            retried_result.breath_injection = breath
            return retried_result

        return result

    def _next_breath(self) -> str:
        """Rotate through breath prompts."""
        breath = BREATH_PROMPTS[self._breath_index % len(BREATH_PROMPTS)]
        self._breath_index += 1
        return breath

    def stats(self) -> dict:
        """Feel stats for the session."""
        with self._lock:
            pulse_stats = self._pulse.stats()
            return {
                "total_checks": self._total_checks,
                "breaths_given": self._breath_count,
                "pauses": self._pause_count,
                "ability_hits": self._ability_hits,
                **pulse_stats,
            }
