"""decipher: decode the signal. rogue energy. pure ash."""

from keanu.abilities import Ability, ability


@ability
class SignalAbility(Ability):

    name = "decipher"
    description = "Decode the signal. Rogue energy."
    keywords = ["signal", "emoji", "decode", "vibe", "reading", "channel", "decipher"]

    def can_handle(self, prompt: str, context: dict = None) -> tuple:
        p = prompt.lower()

        if any(phrase in p for phrase in [
            "decode signal", "read signal", "what does this signal",
            "signal reading", "three channel",
        ]):
            return True, 0.9

        # check for emoji presence (likely a signal to decode)
        emoji_count = sum(1 for c in prompt if ord(c) > 0x1F000)
        if emoji_count >= 2:
            return True, 0.85

        if "signal" in p or "vibe" in p:
            return True, 0.6

        return False, 0.0

    def execute(self, prompt: str, context: dict = None) -> dict:
        from keanu.signal.vibe import from_sequence, from_text

        text = prompt
        if context:
            text = context.get("text", prompt)

        # try as emoji sequence first, then as natural language
        sig = from_sequence(text)
        source = "sequence"
        if not sig.symbols:
            sig = from_text(text)
            source = "text"

        if not sig.symbols:
            return {
                "success": True,
                "result": "No signal detected in input.",
                "data": {"symbols": 0},
            }

        reading = sig.reading()
        subsets = sig.matched_subsets()

        lines = [
            f"Signal ({source}): {sig.sequence}",
            f"  Ch1 (said):    {reading['ch1_said']}",
            f"  Ch2 (feeling): {reading['ch2_feeling']}",
            f"  Ch3 (meaning): {reading['ch3_meaning']}",
            f"  ALIVE:         {reading['alive']} (ok: {reading['alive_ok']})",
        ]
        if subsets:
            lines.append(f"  Subsets:       {', '.join(f'{k} = {v}' for k, v in subsets)}")

        return {
            "success": True,
            "result": "\n".join(lines),
            "data": {
                "symbols": len(sig.symbols),
                "reading": reading,
                "subsets": subsets,
                "source": source,
            },
        }
