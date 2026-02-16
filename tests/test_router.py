"""tests for smart model routing."""

from keanu.router import (
    pick_tier, pick_model, estimate_cost, SessionCost,
    TIERS, ModelTier,
)


class TestPickTier:

    def test_simple_action_read(self):
        assert pick_tier("read file", action="read") == "small"

    def test_simple_action_ls(self):
        assert pick_tier("list files", action="ls") == "small"

    def test_edit_action(self):
        assert pick_tier("edit file", action="edit") == "medium"

    def test_plan_action(self):
        assert pick_tier("plan architecture", action="plan") == "large"

    def test_late_turn_escalation(self):
        assert pick_tier("anything", turn=20) == "large"

    def test_mid_turn_escalation(self):
        assert pick_tier("anything", turn=10) == "medium"

    def test_hard_keywords(self):
        assert pick_tier("refactor the entire system and redesign the architecture") == "large"

    def test_simple_keywords(self):
        assert pick_tier("show what is in the list") == "small"

    def test_long_prompt_large(self):
        assert pick_tier("x " * 300) == "large"

    def test_short_prompt_small(self):
        assert pick_tier("check status") == "small"

    def test_medium_default(self):
        # 100-500 chars, no strong signals either way -> medium
        prompt = "update the user profile page to include a new section for notification preferences and wire it to the settings API"
        assert pick_tier(prompt) == "medium"


class TestPickModel:

    def test_returns_model_id(self):
        model = pick_model("read file", action="read")
        assert "haiku" in model

    def test_large_returns_opus(self):
        model = pick_model("refactor and redesign everything", action="plan")
        assert "opus" in model


class TestEstimateCost:

    def test_basic_cost(self):
        cost = estimate_cost(1000, 500, "medium")
        assert cost > 0

    def test_small_cheaper_than_large(self):
        small = estimate_cost(1000, 500, "small")
        large = estimate_cost(1000, 500, "large")
        assert small < large


class TestSessionCost:

    def test_empty_session(self):
        sc = SessionCost()
        assert sc.calls == 0
        assert sc.estimated_cost == 0.0

    def test_record_call(self):
        sc = SessionCost()
        sc.record(1000, 500, "medium")
        assert sc.calls == 1
        assert sc.prompt_tokens == 1000
        assert sc.response_tokens == 500
        assert sc.estimated_cost > 0

    def test_multiple_calls(self):
        sc = SessionCost()
        sc.record(100, 50, "small")
        sc.record(500, 200, "large")
        assert sc.calls == 2

    def test_summary(self):
        sc = SessionCost()
        sc.record(1000, 500, "medium")
        s = sc.summary()
        assert "1 calls" in s
        assert "$" in s
        assert "tokens" in s


class TestTiers:

    def test_all_tiers_present(self):
        assert "small" in TIERS
        assert "medium" in TIERS
        assert "large" in TIERS

    def test_cost_ordering(self):
        assert TIERS["small"].cost_per_1k < TIERS["medium"].cost_per_1k
        assert TIERS["medium"].cost_per_1k < TIERS["large"].cost_per_1k
