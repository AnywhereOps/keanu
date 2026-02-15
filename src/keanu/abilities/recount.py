"""recount: count what you have. day of reckoning. pure ash."""

from keanu.abilities import Ability, ability


@ability
class StatsAbility(Ability):

    name = "recount"
    description = "Count what you have. Day of reckoning."
    keywords = ["stats", "statistics", "how many", "count", "numbers", "recount"]

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        p = prompt.lower()

        if any(phrase in p for phrase in [
            "memory stats", "how many memories", "show stats",
            "memory count", "how many goals",
        ]):
            return True, 0.9

        if "stats" in p or "statistics" in p:
            return True, 0.7

        if "how many" in p and any(w in p for w in ["memor", "plan", "goal", "tag"]):
            return True, 0.75

        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        from keanu.memory import MemberberryStore

        store = MemberberryStore()
        s = store.stats()

        lines = [f"Memories: {s['total_memories']}"]
        for t, c in s["memories_by_type"].items():
            lines.append(f"  {t}: {c}")
        lines.append(f"Plans: {s['total_plans']}")
        for st, c in s["plans_by_status"].items():
            lines.append(f"  {st}: {c}")
        tags = s["unique_tags"]
        lines.append(f"Tags: {len(tags)} ({', '.join(tags[:10])}{'...' if len(tags) > 10 else ''})")

        return {
            "success": True,
            "result": "\n".join(lines),
            "data": s,
        }
