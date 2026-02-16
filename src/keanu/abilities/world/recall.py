"""recall: summon memories from the log. pure ash.

in the world: walk the riverbank. what you dropped is still there.
"""

from keanu.abilities import Ability, ability


@ability
class RecallAbility(Ability):

    name = "recall"
    description = "Summon memories. They come to you."
    keywords = ["recall", "remember", "what did i", "have i", "memory", "past", "goals"]
    cast_line = "recall reaches into the deep..."

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        p = prompt.lower()

        if any(phrase in p for phrase in [
            "what did i", "do i remember", "have i done", "recall",
            "what are my goals", "what have i decided",
        ]):
            return True, 0.85

        if any(kw in p for kw in self.keywords):
            return True, 0.6

        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        from keanu.log import recall

        results = recall(query=prompt, limit=5)

        if not results:
            return {
                "success": True,
                "result": "No relevant memories found.",
                "data": {"count": 0},
            }

        lines = [f"Found {len(results)} relevant memories:\n"]
        for m in results:
            content = m.get("content", "")
            mtype = m.get("memory_type", "")
            # log entries store memory_type in attrs
            if (not mtype or mtype == "log") and m.get("attrs"):
                mtype = m["attrs"].get("memory_type", mtype)
            lines.append(f"- [{mtype}] {content}")
            ctx = m.get("context", "")
            if ctx:
                lines.append(f"  context: {ctx}")

        return {
            "success": True,
            "result": "\n".join(lines),
            "data": {"count": len(results)},
        }
