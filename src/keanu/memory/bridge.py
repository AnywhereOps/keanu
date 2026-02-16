"""bridge.py - memory capture helpers.

detects when something is worth remembering, figures out what kind of memory
it is. simple keyword matching, no LLM needed.

in the world: the sieve. not everything that passes through deserves to stay.
this decides what sticks.
"""

from keanu.log import info


# words that signal "this matters, remember it"
CAPTURE_TRIGGERS = [
    "remember", "don't forget", "important:", "note to self",
    "always ", "never ", "prefer", "decision:", "lesson:",
    "i want", "i need", "my goal", "the plan is",
]

# what kind of memory is it?
CATEGORY_RULES = [
    ("preference", ["prefer", "like", "hate", "want", "need", "love", "rather"]),
    ("decision", ["decided", "will use", "going with", "chose", "picking"]),
    ("goal", ["goal", "plan to", "want to", "going to build", "shipping"]),
    ("lesson", ["learned", "lesson", "mistake", "never again", "turns out"]),
    ("commitment", ["promise", "commit", "deadline", "by friday", "by monday"]),
    ("fact", ["is", "are", "has", "have", "lives in", "works at"]),
]


def detect_category(text: str) -> str:
    """match text to a memory type by keywords."""
    lower = text.lower()
    for category, keywords in CATEGORY_RULES:
        if any(kw in lower for kw in keywords):
            return category
    return "fact"


def should_capture(text: str) -> bool:
    """does this text contain a trigger word worth remembering?"""
    lower = text.lower()
    return any(trigger in lower for trigger in CAPTURE_TRIGGERS)


def capture_from_conversation(messages: list[str]) -> list[dict]:
    """scan a conversation for things worth keeping. max 5.

    in the world: panning for gold. most words wash through.
    the ones that catch the light get stored.
    """
    captures = []
    for msg in messages:
        if not should_capture(msg):
            continue
        category = detect_category(msg)
        captures.append({
            "content": msg.strip(),
            "memory_type": category,
            "importance": 7 if category in ("goal", "commitment", "decision") else 5,
        })
        if len(captures) >= 5:
            break
    info("bridge", f"captured {len(captures)} memories from conversation")
    return captures
