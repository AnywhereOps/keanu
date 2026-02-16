"""fuse.py - convergence as an ability.

takes a question. reads it through six lenses (3 axes x 2 poles).
pushes each lens to full expression. converges at the threshold.

practically: "converge these perspectives" runs the six lens pipeline and
returns the synthesis.

in the world: the fusion reactor. six witnesses speak, the threshold listens,
and says what only it can see.
"""

from keanu.abilities import Ability, ability
from keanu.log import info


@ability
class FuseAbility(Ability):
    """convergence synthesis. six lenses, full expression, then threshold."""

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

        if not result.ok:
            return {
                "success": False,
                "result": f"Could not converge: {result.error or 'no synthesis produced'}",
                "data": {},
            }

        # build readable output
        lines = []
        if result.one_line:
            lines.append(result.one_line)
        if result.synthesis and result.synthesis != result.one_line:
            lines.append("")
            lines.append(result.synthesis)
        if result.tensions:
            lines.append("")
            lines.append("Unresolved tensions:")
            for t in result.tensions:
                lines.append(f"  - {t}")
        if result.what_changes:
            lines.append("")
            lines.append(f"What changes: {result.what_changes}")

        # lens summary
        lines.append("")
        lines.append("Lens readings:")
        for r in result.readings:
            status = " [BLACK]" if r.black else ""
            lines.append(f"  {r.name}: {r.turns} turns, {r.score:.1f}/10{status}")

        return {
            "success": True,
            "result": "\n".join(lines),
            "data": {
                "readings": [
                    {"lens": r.lens, "turns": r.turns, "score": r.score}
                    for r in result.readings
                ],
                "synthesis": result.synthesis,
                "one_line": result.one_line,
                "tensions": result.tensions,
                "graph_context": result.graph_context,
            },
        }
