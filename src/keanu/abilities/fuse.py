"""fuse.py - convergence as an ability.

takes a question. splits it across two orthogonal dualities.
synthesizes each side through the oracle. converges the syntheses
into something neither could reach alone.

this is the first ability that uses fire. every other ability is ash,
local and deterministic. fuse reaches through the oracle because
convergence needs open possibility space to synthesize.

in the world: the fusion reactor. two opposing truths go in, one new truth comes out.
"""

from keanu.abilities import Ability, ability
from keanu.log import info


@ability
class FuseAbility(Ability):
    """Convergence synthesis. The one ability that uses fire."""

    name = "fuse"
    description = "Converge opposing perspectives into new truth."
    keywords = [
        "converge", "convergence", "synthesize", "synthesis",
        "duality", "dualities", "both sides", "fuse",
        "opposing views", "tensions", "perspectives",
    ]

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        p = prompt.lower()

        # strong signals
        if any(phrase in p for phrase in [
            "converge", "convergence", "fuse this", "synthesize",
            "both sides", "find the synthesis",
        ]):
            return True, 0.85

        # keyword match
        hits = sum(1 for kw in self.keywords if kw in p)
        if hits >= 2:
            return True, 0.7

        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        from keanu.converge.engine import run as run_convergence

        legend = "creator"
        model = None
        if context:
            legend = context.get("legend", legend)
            model = context.get("model", model)

        info("fuse", f"converging: {prompt[:80]}")

        result = run_convergence(prompt, legend=legend, model=model)

        if result is None:
            return {
                "success": False,
                "result": "Could not converge. Either the graph found no dualities or the oracle couldn't be reached.",
                "data": {},
            }

        final = result.get("final", {})
        convergence = final.get("convergence", "")
        one_line = final.get("one_line", "")
        implications = final.get("implications", [])
        what_changes = final.get("what_changes", "")

        # build readable output
        lines = []
        if one_line:
            lines.append(one_line)
        if convergence and convergence != one_line:
            lines.append("")
            lines.append(convergence)
        if implications:
            lines.append("")
            for imp in implications:
                lines.append(f"- {imp}")
        if what_changes:
            lines.append("")
            lines.append(f"What changes: {what_changes}")

        return {
            "success": True,
            "result": "\n".join(lines) if lines else "Convergence complete but no synthesis text returned.",
            "data": {
                "split_source": result.get("split_source", ""),
                "dualities": result.get("dualities", {}),
                "convergence_1": result.get("convergence_1", {}),
                "convergence_2": result.get("convergence_2", {}),
                "final": final,
            },
        }
