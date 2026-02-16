"""scry: see hidden patterns without touching the source. pure ash."""

from keanu.abilities import Ability, ability


@ability
class DetectAbility(Ability):

    name = "scry"
    description = "See hidden patterns without touching the source"
    keywords = ["detect", "check for", "scan for", "sycophancy", "empathy", "pattern", "scry"]
    cast_line = "scry peers into the weave..."

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        p = prompt.lower()

        # check for specific pattern names
        from keanu.detect import DETECTORS
        if any(d in p for d in DETECTORS):
            return True, 0.9

        if any(phrase in p for phrase in ["detect", "check for", "scan for"]):
            return True, 0.7

        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        from keanu.detect import DETECTORS
        from keanu.detect.engine import scan

        p = prompt.lower()

        # figure out which pattern to detect
        pattern = None
        for d in DETECTORS:
            if d in p:
                pattern = d
                break

        if not pattern:
            pattern = "empathy_frustrated"  # reasonable default

        # get text to scan: from context, or from the prompt itself
        text = prompt
        if context:
            text = context.get("text", prompt)

        lines = text.split("\n")

        try:
            notices = scan(lines, pattern)
        except Exception as e:
            return {
                "success": False,
                "result": f"Detection failed: {e}",
                "data": {},
            }

        if not notices:
            return {
                "success": True,
                "result": f"No {pattern} detected.",
                "data": {"pattern": pattern, "count": 0},
            }

        result_lines = [f"Detected {len(notices)} instances of {pattern}:\n"]
        for n in notices[:5]:
            result_lines.append(f"- Line {n.line_num}: {n.text[:80]}")
            result_lines.append(f"  {n.detail}")

        return {
            "success": True,
            "result": "\n".join(result_lines),
            "data": {"pattern": pattern, "count": len(notices)},
        }
