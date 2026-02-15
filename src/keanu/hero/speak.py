"""speak.py - the communicator. translates across audiences.

takes content and a target audience, rewrites it so that audience
can understand it. preserves meaning, changes vocabulary and depth.

practically: "speak this to a friend" rewrites technical content in plain talk.

in the world: the speaker crosses boundaries. same truth, different tongue.
"""

from dataclasses import dataclass, field

from keanu.oracle import call_oracle, interpret
from keanu.hero.feel import Feel
from keanu.log import info, warn


SPEAK_PROMPT = """You are a translator between audiences. You rewrite content
so a specific audience can understand it. You preserve the meaning exactly.
You change the vocabulary, depth, and framing to match who's reading.

Target audience: {audience}

Respond with JSON:
{{
    "translation": "the rewritten content",
    "key_shifts": ["what you changed and why, one per shift"]
}}

Rules:
- Preserve all factual content. Don't simplify by removing.
- No disclaimers, no filler, no "in other words" intros.
- Match the audience's vocabulary. A friend doesn't say "leverage". An executive doesn't need implementation details.
- If the content is already appropriate for the audience, say so and return it unchanged.
- key_shifts should be 1-4 items explaining what you adapted."""

AUDIENCES = {
    "friend": "A regular person. No jargon, no corporate speak. Talk like you're explaining to someone you trust over coffee.",
    "executive": "A decision maker. Lead with impact and numbers. Skip implementation details. What changed, what it means, what's next.",
    "junior-dev": "A developer in their first year. Explain the why, not just the what. Define terms they might not know yet.",
    "5-year-old": "A five year old child. Use simple analogies. One idea per sentence. Concrete, not abstract.",
    "architect": "Drew. He knows the codebase, the philosophy, the history. No hand-holding. Keep it 100.",
}


@dataclass
class SpeakResult:
    """what came back from speaking.

    in the world: the original tongue and the translation, side by side.
    """
    original: str
    audience: str
    translation: str = ""
    key_shifts: list = field(default_factory=list)
    raw: str = ""
    feel_stats: dict = field(default_factory=dict)
    error: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.translation) and not self.error


def speak(content: str, audience: str = "friend", legend: str = "creator",
          model: str = None) -> SpeakResult:
    """translate content for an audience. one oracle call.

    takes content and an audience name (or custom description). asks the
    oracle to rewrite it for that audience. feel checks the response.

    in the world: open your mouth. speak their language. mean the same thing.
    """
    feel = Feel()

    audience_desc = AUDIENCES.get(audience, audience)
    system = SPEAK_PROMPT.format(audience=audience_desc)

    info("speak", f"speaking to {audience}: {content[:60]}")

    try:
        response = call_oracle(content, system, legend=legend, model=model)
    except ConnectionError as e:
        warn("speak", f"oracle unreachable: {e}")
        return SpeakResult(
            original=content, audience=audience,
            error=str(e), feel_stats=feel.stats(),
        )

    feel_result = feel.check(response)

    if feel_result.should_pause:
        warn("speak", "black state in speak response")
        return SpeakResult(
            original=content, audience=audience,
            error="black state", feel_stats=feel.stats(),
        )

    try:
        parsed = interpret(response)
    except Exception:
        return SpeakResult(
            original=content, audience=audience, raw=response,
            error="couldn't parse oracle response",
            feel_stats=feel.stats(),
        )

    translation = parsed.get("translation", "")
    shifts = parsed.get("key_shifts", [])

    info("speak", f"spoke to {audience}, {len(shifts)} shifts")

    return SpeakResult(
        original=content,
        audience=audience,
        translation=translation,
        key_shifts=shifts,
        raw=response,
        feel_stats=feel.stats(),
    )
