"""inspect: inspect target. gear, stats, everything. pure ash."""

from keanu.abilities import Ability, ability


@ability
class HealthAbility(Ability):

    name = "inspect"
    description = "Inspect target. Gear, stats, everything."
    keywords = ["health", "healthz", "status", "system check", "diagnostic", "is everything ok", "inspect"]

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        p = prompt.lower()

        if any(phrase in p for phrase in [
            "health check", "system status", "is everything ok",
            "healthz", "system health",
        ]):
            return True, 0.9

        if "health" in p or "status" in p:
            return True, 0.6

        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        results = {}

        # memory health
        try:
            from keanu.memory import MemberberryStore
            store = MemberberryStore()
            stats = store.stats()
            results["memory"] = {
                "ok": True,
                "total": stats["total_memories"],
                "plans": stats["total_plans"],
                "tags": len(stats["unique_tags"]),
            }
        except Exception as e:
            results["memory"] = {"ok": False, "error": str(e)}

        # module availability
        modules = {
            "scan": "keanu.scan.helix",
            "detect": "keanu.detect.engine",
            "compress": "keanu.compress.dns",
            "converge": "keanu.converge.engine",
            "signal": "keanu.signal",
            "memory": "keanu.memory.memberberry",
            "alive": "keanu.alive",
        }
        mod_status = {}
        for name, path in modules.items():
            try:
                __import__(path)
                mod_status[name] = "ok"
            except ImportError:
                mod_status[name] = "missing"
            except Exception:
                mod_status[name] = "error"
        results["modules"] = mod_status

        # external deps
        deps = {}
        for dep in ["chromadb", "requests"]:
            try:
                __import__(dep)
                deps[dep] = "installed"
            except ImportError:
                deps[dep] = "missing"
        results["deps"] = deps

        # abilities
        from keanu.abilities import list_abilities
        abilities = list_abilities()
        results["abilities"] = len(abilities)

        # build summary
        mod_ok = sum(1 for v in mod_status.values() if v == "ok")
        mod_total = len(mod_status)
        mem_ok = results["memory"].get("ok", False)

        lines = [
            f"Health: {mod_ok}/{mod_total} modules, "
            f"{'memory ok' if mem_ok else 'memory down'}, "
            f"{len(abilities)} abilities",
        ]

        for name, status in mod_status.items():
            marker = "OK" if status == "ok" else status.upper()
            lines.append(f"  {name:<12} {marker}")

        if mem_ok:
            m = results["memory"]
            lines.append(f"  memories: {m['total']} | plans: {m['plans']} | tags: {m['tags']}")

        return {
            "success": True,
            "result": "\n".join(lines),
            "data": results,
        }
