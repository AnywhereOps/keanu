"""router.py - smart model routing.

picks the right model for the task. simple things get a small model,
hard things get the full brain. the goal: spend less fire where ash
would do, and more fire where it matters.

in the world: don't use a forge hammer to hang a picture frame.
"""

from dataclasses import dataclass


@dataclass
class ModelTier:
    """a model size category."""
    name: str        # "small", "medium", "large"
    model: str       # actual model ID
    max_tokens: int  # context limit
    cost_per_1k: float  # rough cost estimate


# default tiers (anthropic). can be overridden per-legend.
TIERS = {
    "small": ModelTier("small", "claude-haiku-4-5-20251001", 200_000, 0.001),
    "medium": ModelTier("medium", "claude-sonnet-4-5-20250929", 200_000, 0.003),
    "large": ModelTier("large", "claude-opus-4-6", 200_000, 0.015),
}

# keywords that signal complexity
_SIMPLE_SIGNALS = {
    "read", "cat", "show", "list", "ls", "dir", "find",
    "grep", "search", "count", "check", "status", "diff",
    "what is", "where is", "how many",
}

_HARD_SIGNALS = {
    "refactor", "redesign", "architect", "rewrite", "migrate",
    "debug", "investigate", "analyze", "explain why",
    "multi-file", "across", "system", "complex",
    "plan", "strategy", "trade-off", "tradeoff",
}


def pick_tier(task: str, action: str = "", turn: int = 0,
              context: dict = None) -> str:
    """pick the right model tier for a task.

    returns "small", "medium", or "large".

    heuristics:
    - simple file ops and lookups -> small
    - single-file edits and analysis -> medium
    - multi-file refactors, planning, debugging -> large
    - late turns (> 15) in a loop -> bump up (agent is struggling)
    """
    task_lower = task.lower()

    # action-based routing (fastest path)
    if action in ("read", "ls", "search", "grep"):
        return "small"
    if action in ("write", "edit"):
        return "medium"
    if action in ("plan", "dream", "converge"):
        return "large"

    # turn-based escalation
    if turn > 15:
        return "large"
    if turn > 8:
        return "medium"

    # keyword-based routing
    words = set(task_lower.split())

    hard_count = sum(1 for s in _HARD_SIGNALS if s in task_lower)
    simple_count = sum(1 for s in _SIMPLE_SIGNALS if s in task_lower)

    if hard_count >= 2:
        return "large"
    if simple_count >= 2 and hard_count == 0:
        return "small"

    # length heuristic: long prompts tend to be complex
    if len(task) > 500:
        return "large"
    if len(task) < 100:
        return "small"

    return "medium"


def pick_model(task: str, action: str = "", turn: int = 0,
               context: dict = None) -> str:
    """pick the actual model ID for a task."""
    tier = pick_tier(task, action, turn, context)
    return TIERS[tier].model


def estimate_cost(prompt_tokens: int, response_tokens: int,
                  tier: str = "medium") -> float:
    """rough cost estimate for a call."""
    t = TIERS.get(tier, TIERS["medium"])
    total_tokens = prompt_tokens + response_tokens
    return (total_tokens / 1000) * t.cost_per_1k


@dataclass
class SessionCost:
    """tracks cost for a session."""
    calls: int = 0
    prompt_tokens: int = 0
    response_tokens: int = 0
    estimated_cost: float = 0.0

    def record(self, prompt_tokens: int, response_tokens: int, tier: str = "medium"):
        """record a call."""
        self.calls += 1
        self.prompt_tokens += prompt_tokens
        self.response_tokens += response_tokens
        self.estimated_cost += estimate_cost(prompt_tokens, response_tokens, tier)

    def summary(self) -> str:
        """one-line cost summary."""
        return (
            f"{self.calls} calls, "
            f"~{self.prompt_tokens + self.response_tokens:,} tokens, "
            f"~${self.estimated_cost:.4f}"
        )
