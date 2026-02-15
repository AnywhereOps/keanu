"""recall: summon memories. they come to you. pure ash."""

from keanu.abilities import Ability, ability


@ability
class RecallAbility(Ability):

    name = "recall"
    description = "Summon memories. They come to you."
    keywords = ["recall", "remember", "what did i", "have i", "memory", "past", "goals"]

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
        from keanu.memory import MemberberryStore

        store = MemberberryStore()
        results = store.recall(query=prompt, limit=5)

        if not results:
            return {
                "success": True,
                "result": "No relevant memories found.",
                "data": {"count": 0},
            }

        lines = [f"Found {len(results)} relevant memories:\n"]
        for m in results:
            mtype = m.get("memory_type", "")
            content = m.get("content", "")
            lines.append(f"- [{mtype}] {content}")
            if m.get("context"):
                lines.append(f"  context: {m['context']}")

        return {
            "success": True,
            "result": "\n".join(lines),
            "data": {"count": len(results)},
        }
