"""soulstone: capture the essence, store it. pure warlock. pure ash."""

from keanu.abilities import Ability, ability


@ability
class CompressAbility(Ability):

    name = "soulstone"
    description = "Capture the essence, store it. Pure warlock."
    keywords = ["compress", "coef", "dns", "hash", "barcode", "store content", "soulstone"]

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        p = prompt.lower()

        if any(phrase in p for phrase in [
            "compress this", "coef compress", "store this content",
            "content hash", "barcode",
        ]):
            return True, 0.9

        if "compress" in p or "coef" in p:
            return True, 0.7

        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        from keanu.compress.dns import ContentDNS

        text = prompt
        if context:
            text = context.get("text", prompt)
            if context.get("file_path"):
                try:
                    with open(context["file_path"]) as f:
                        text = f.read()
                except (OSError, IOError) as e:
                    return {
                        "success": False,
                        "result": f"Could not read file: {e}",
                        "data": {},
                    }

        store = ContentDNS()
        h = store.store(text)

        return {
            "success": True,
            "result": f"Stored: {h[:16]} ({len(text)} chars)",
            "data": {
                "hash": h,
                "hash_short": h[:16],
                "size": len(text),
            },
        }
