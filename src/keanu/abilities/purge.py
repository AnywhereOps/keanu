"""purge: check for debuffs. grey and black are debuffs. pure ash."""

from keanu.abilities import Ability, ability


@ability
class AliveAbility(Ability):

    name = "purge"
    description = "Check for debuffs. Grey and black are debuffs."
    keywords = ["alive", "grey", "black", "cognitive", "state", "diagnose", "is this alive", "purge", "debuff"]

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        p = prompt.lower()

        if any(phrase in p for phrase in [
            "is this alive", "alive check", "alive diagnostic",
            "grey or black", "cognitive state", "alive or grey",
        ]):
            return True, 0.9

        # "alive" alone is common English, require a second signal
        if "alive" in p and any(w in p for w in [
            "check", "diagnose", "text", "grey", "black", "state",
        ]):
            return True, 0.8

        if any(kw in p for kw in ["alive", "grey", "black"]):
            if context and context.get("text"):
                return True, 0.7
            if len(p) > 50:
                return True, 0.6

        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        from keanu.alive import diagnose

        text = prompt
        if context:
            text = context.get("text", prompt)

        reading = diagnose(text)

        return {
            "success": True,
            "result": reading.summary(),
            "data": reading.to_dict(),
        }
