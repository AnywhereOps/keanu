"""Tests for memory/memberberry.py - remember, recall, plan."""

import json
import os
import tempfile
from unittest.mock import patch

from keanu.memory.memberberry import (
    Memory,
    MemoryType,
    MemberberryStore,
    PlanGenerator,
    Plan,
    Action,
)


def _tmp_store():
    """Create a store in a temp directory."""
    tmpdir = tempfile.mkdtemp()
    with patch("keanu.memory.memberberry.MEMBERBERRY_DIR", tmpdir), \
         patch("keanu.memory.memberberry.MEMORIES_FILE", os.path.join(tmpdir, "memories.json")), \
         patch("keanu.memory.memberberry.PLANS_FILE", os.path.join(tmpdir, "plans.json")), \
         patch("keanu.memory.memberberry.CONFIG_FILE", os.path.join(tmpdir, "config.json")):
        store = MemberberryStore()
    # Point instance at temp files directly
    return store, tmpdir


class TestMemory:
    def test_memory_creates_id(self):
        m = Memory(content="test", memory_type="goal")
        assert m.id
        assert len(m.id) == 12

    def test_memory_creates_timestamp(self):
        m = Memory(content="test", memory_type="fact")
        assert m.created_at

    def test_memory_type_enum(self):
        assert MemoryType.GOAL.value == "goal"
        assert MemoryType.LESSON.value == "lesson"
        assert len(MemoryType) == 7

    def test_relevance_score_base(self):
        m = Memory(content="build something", memory_type="goal", importance=8)
        score = m.relevance_score()
        assert score > 0

    def test_relevance_score_tag_overlap(self):
        m = Memory(content="test", memory_type="goal", tags=["build", "career"])
        score_with = m.relevance_score(query_tags=["build"])
        score_without = m.relevance_score(query_tags=["unrelated"])
        assert score_with > score_without

    def test_relevance_score_text_match(self):
        m = Memory(content="ship the product", memory_type="goal")
        score_match = m.relevance_score(query_text="ship product")
        score_none = m.relevance_score(query_text="unrelated query")
        assert score_match > score_none

    def test_relevance_type_weight(self):
        goal = Memory(content="x", memory_type="goal", importance=5)
        fact = Memory(content="x", memory_type="fact", importance=5)
        assert goal.relevance_score() > fact.relevance_score()


class TestStore:
    def test_remember_and_recall(self, tmp_path):
        with patch("keanu.memory.memberberry.MEMBERBERRY_DIR", tmp_path), \
             patch("keanu.memory.memberberry.MEMORIES_FILE", tmp_path / "memories.json"), \
             patch("keanu.memory.memberberry.PLANS_FILE", tmp_path / "plans.json"), \
             patch("keanu.memory.memberberry.CONFIG_FILE", tmp_path / "config.json"):
            store = MemberberryStore()
            m = Memory(content="ship v1", memory_type="goal", tags=["build"])
            mid = store.remember(m)
            assert mid == m.id

            results = store.recall(query="ship")
            assert len(results) == 1
            assert results[0]["content"] == "ship v1"

    def test_forget(self, tmp_path):
        with patch("keanu.memory.memberberry.MEMBERBERRY_DIR", tmp_path), \
             patch("keanu.memory.memberberry.MEMORIES_FILE", tmp_path / "memories.json"), \
             patch("keanu.memory.memberberry.PLANS_FILE", tmp_path / "plans.json"), \
             patch("keanu.memory.memberberry.CONFIG_FILE", tmp_path / "config.json"):
            store = MemberberryStore()
            m = Memory(content="forget me", memory_type="fact")
            mid = store.remember(m)
            assert store.forget(mid)
            assert not store.forget("nonexistent")
            assert len(store.recall()) == 0

    def test_stats(self, tmp_path):
        with patch("keanu.memory.memberberry.MEMBERBERRY_DIR", tmp_path), \
             patch("keanu.memory.memberberry.MEMORIES_FILE", tmp_path / "memories.json"), \
             patch("keanu.memory.memberberry.PLANS_FILE", tmp_path / "plans.json"), \
             patch("keanu.memory.memberberry.CONFIG_FILE", tmp_path / "config.json"):
            store = MemberberryStore()
            store.remember(Memory(content="a", memory_type="goal", tags=["x"]))
            store.remember(Memory(content="b", memory_type="fact", tags=["y"]))
            s = store.stats()
            assert s["total_memories"] == 2
            assert "goal" in s["memories_by_type"]
            assert "x" in s["unique_tags"]

    def test_get_all_tags(self, tmp_path):
        with patch("keanu.memory.memberberry.MEMBERBERRY_DIR", tmp_path), \
             patch("keanu.memory.memberberry.MEMORIES_FILE", tmp_path / "memories.json"), \
             patch("keanu.memory.memberberry.PLANS_FILE", tmp_path / "plans.json"), \
             patch("keanu.memory.memberberry.CONFIG_FILE", tmp_path / "config.json"):
            store = MemberberryStore()
            store.remember(Memory(content="a", memory_type="goal", tags=["alpha", "beta"]))
            store.remember(Memory(content="b", memory_type="fact", tags=["beta", "gamma"]))
            tags = store.get_all_tags()
            assert tags == ["alpha", "beta", "gamma"]


class TestPlanGenerator:
    def test_generate_plan(self, tmp_path):
        with patch("keanu.memory.memberberry.MEMBERBERRY_DIR", tmp_path), \
             patch("keanu.memory.memberberry.MEMORIES_FILE", tmp_path / "memories.json"), \
             patch("keanu.memory.memberberry.PLANS_FILE", tmp_path / "plans.json"), \
             patch("keanu.memory.memberberry.CONFIG_FILE", tmp_path / "config.json"):
            store = MemberberryStore()
            store.remember(Memory(content="ship it", memory_type="goal", tags=["build"]))
            store.remember(Memory(content="never skip tests", memory_type="lesson", tags=["build"]))
            store.remember(Memory(content="deploy friday", memory_type="commitment", tags=["build"]))

            planner = PlanGenerator(store)
            plan = planner.generate_plan("what to do next", tags=["build"])
            assert plan.title
            assert len(plan.actions) >= 2  # goal + commitment at minimum
            assert plan.status == "draft"

    def test_plan_stored_in_store(self, tmp_path):
        with patch("keanu.memory.memberberry.MEMBERBERRY_DIR", tmp_path), \
             patch("keanu.memory.memberberry.MEMORIES_FILE", tmp_path / "memories.json"), \
             patch("keanu.memory.memberberry.PLANS_FILE", tmp_path / "plans.json"), \
             patch("keanu.memory.memberberry.CONFIG_FILE", tmp_path / "config.json"):
            store = MemberberryStore()
            store.remember(Memory(content="test goal", memory_type="goal"))
            planner = PlanGenerator(store)
            planner.generate_plan("test")
            plans = store.get_plans()
            assert len(plans) == 1


class TestAction:
    def test_action_creates_id(self):
        a = Action(description="do the thing")
        assert a.id
        assert len(a.id) == 8


class TestPlan:
    def test_plan_creates_id(self):
        p = Plan(title="test plan")
        assert p.id
        assert len(p.id) == 12
