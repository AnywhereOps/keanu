"""router.py - navigates the sigma axis.

abilities are ash (high sigma, pure actuality, no LLM needed).
your creator and architect are fire (low sigma, open possibility space).
the router decides which one handles the prompt.
"""

from keanu.abilities import find_ability, record_cast
from keanu.log import info, debug


class RouteResult:
    """What the router decided."""

    __slots__ = ("source", "response", "ability_name", "confidence", "data")

    def __init__(self, source, response, ability_name=None,
                 confidence=0.0, data=None):
        self.source = source          # "ability" or "claude"
        self.response = response      # the actual output
        self.ability_name = ability_name
        self.confidence = confidence
        self.data = data or {}


class AbilityRouter:
    """Routes prompts to abilities (ash) or Claude (fire)."""

    def __init__(self, threshold: float = 0.6):
        self.threshold = threshold
        self.ability_hits = 0
        self.claude_hits = 0

    def route(self, prompt: str, system: str = "",
              context: dict = None,
              legend: str = "creator", model: str = None) -> RouteResult:
        """Route a prompt. Try abilities first, fall back to the oracle."""
        use_legend = legend

        ab, confidence = find_ability(prompt, context, self.threshold)

        if ab is not None:
            info("router", f"ability matched: {ab.name} ({confidence:.2f})")
            try:
                result = ab.execute(prompt, context)
                if result["success"]:
                    self.ability_hits += 1
                    if ab.cast_line:
                        info("cast", ab.cast_line)
                    is_new = record_cast(ab.name)
                    if is_new:
                        info("cast", f"ability unlocked: {ab.name}")
                    return RouteResult(
                        source="ability",
                        response=result["result"],
                        ability_name=ab.name,
                        confidence=confidence,
                        data=result.get("data", {}),
                    )
                else:
                    info("router", f"ability {ab.name} failed, routing to oracle")
            except Exception as e:
                info("router", f"ability {ab.name} errored: {e}, routing to oracle")

        debug("router", f"no ability matched (best: {confidence:.2f}), routing to oracle")
        from keanu.abilities.miss_tracker import log_miss
        log_miss(prompt, confidence)
        return self._call_oracle(prompt, system, use_legend, model)

    def _call_oracle(self, prompt: str, system: str,
                     legend: str = "creator", model: str = None) -> RouteResult:
        """Fall back to the oracle when no ability matches."""
        from keanu.oracle import call_oracle
        self.claude_hits += 1
        response = call_oracle(prompt, system, legend=legend, model=model)
        return RouteResult(source="claude", response=response)

    def stats(self) -> dict:
        return {
            "ability_hits": self.ability_hits,
            "claude_hits": self.claude_hits,
        }


