"""Tests for memory/memberberry.py - remember, recall, plan."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from keanu.memory.memberberry import (
    Memory,
    MemoryType,
    MemberberryStore,
    PlanGenerator,
    Plan,
    Action,
)
from keanu.memory.disagreement import Disagreement, DisagreementTracker
from keanu.memory.bridge import recall_via_openpaw, openpaw_available


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

    def test_deprioritize(self, tmp_path):
        with patch("keanu.memory.memberberry.MEMBERBERRY_DIR", tmp_path), \
             patch("keanu.memory.memberberry.MEMORIES_FILE", tmp_path / "memories.json"), \
             patch("keanu.memory.memberberry.PLANS_FILE", tmp_path / "plans.json"), \
             patch("keanu.memory.memberberry.CONFIG_FILE", tmp_path / "config.json"):
            store = MemberberryStore()
            m = Memory(content="lower me", memory_type="fact", importance=8)
            mid = store.remember(m)
            assert store.deprioritize(mid)
            assert not store.deprioritize("nonexistent")
            # memory still exists, just importance=1
            results = store.recall()
            assert len(results) == 1
            assert results[0]["importance"] == 1

    def test_dedup(self, tmp_path):
        with patch("keanu.memory.memberberry.MEMBERBERRY_DIR", tmp_path), \
             patch("keanu.memory.memberberry.MEMORIES_FILE", tmp_path / "memories.json"), \
             patch("keanu.memory.memberberry.PLANS_FILE", tmp_path / "plans.json"), \
             patch("keanu.memory.memberberry.CONFIG_FILE", tmp_path / "config.json"):
            store = MemberberryStore()
            m1 = Memory(content="same content", memory_type="goal")
            m2 = Memory(content="same content", memory_type="goal")
            id1 = store.remember(m1)
            id2 = store.remember(m2)
            assert id1 == id2
            assert len(store.memories) == 1

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


class TestJSONL:
    def test_load_jsonl(self, tmp_path):
        jsonl_file = tmp_path / "test.jsonl"
        jsonl_file.write_text(
            '{"id":"abc","content":"first","memory_type":"goal"}\n'
            '{"id":"def","content":"second","memory_type":"fact"}\n'
        )
        records = MemberberryStore._load_jsonl(jsonl_file)
        assert len(records) == 2
        assert records[0]["content"] == "first"
        assert records[1]["content"] == "second"

    def test_load_jsonl_with_updates(self, tmp_path):
        jsonl_file = tmp_path / "test.jsonl"
        jsonl_file.write_text(
            '{"id":"abc","content":"first","importance":5}\n'
            '{"id":"abc","importance":1,"_update":true,"_updated_at":"2026-02-14"}\n'
        )
        records = MemberberryStore._load_jsonl(jsonl_file)
        assert len(records) == 1
        assert records[0]["importance"] == 1
        assert records[0]["content"] == "first"

    def test_append_jsonl(self, tmp_path):
        jsonl_file = tmp_path / "sub" / "test.jsonl"
        MemberberryStore._append_jsonl(jsonl_file, {"id": "abc", "content": "test"})
        MemberberryStore._append_jsonl(jsonl_file, {"id": "def", "content": "test2"})
        lines = jsonl_file.read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["id"] == "abc"

    def test_append_strips_underscore_fields(self, tmp_path):
        jsonl_file = tmp_path / "test.jsonl"
        MemberberryStore._append_jsonl(jsonl_file, {"id": "abc", "_relevance_score": 0.5, "content": "x"})
        line = json.loads(jsonl_file.read_text().strip())
        assert "_relevance_score" not in line
        assert line["content"] == "x"

    def test_shard_path(self, tmp_path):
        path = MemberberryStore._shard_path(tmp_path, "drew")
        assert "drew" in str(path)
        assert path.suffix == ".jsonl"


class TestDisagreement:
    def test_disagreement_creates_id(self):
        d = Disagreement(topic="test", human_text="yes", ai_text="no")
        assert d.id
        assert len(d.id) == 12
        assert d.resolution == "unresolved"

    def test_disagreement_creates_timestamp(self):
        d = Disagreement(topic="test", human_text="yes", ai_text="no")
        assert d.timestamp

    def test_tracker_record(self, tmp_path):
        with patch("keanu.memory.memberberry.MEMBERBERRY_DIR", tmp_path), \
             patch("keanu.memory.memberberry.MEMORIES_FILE", tmp_path / "memories.json"), \
             patch("keanu.memory.memberberry.PLANS_FILE", tmp_path / "plans.json"), \
             patch("keanu.memory.memberberry.CONFIG_FILE", tmp_path / "config.json"):
            store = MemberberryStore()
            tracker = DisagreementTracker(store)
            with patch("keanu.detect.engine.detect_emotion", return_value=[]):
                d = tracker.record("regex vs vectors", "regex is fine", "vectors for consistency")
            assert d.topic == "regex vs vectors"
            assert d.id
            assert len(store.memories) == 1
            assert store.memories[0]["memory_type"] == "decision"
            assert "disagreement" in store.memories[0]["tags"]

    def test_tracker_resolve(self, tmp_path):
        with patch("keanu.memory.memberberry.MEMBERBERRY_DIR", tmp_path), \
             patch("keanu.memory.memberberry.MEMORIES_FILE", tmp_path / "memories.json"), \
             patch("keanu.memory.memberberry.PLANS_FILE", tmp_path / "plans.json"), \
             patch("keanu.memory.memberberry.CONFIG_FILE", tmp_path / "config.json"):
            store = MemberberryStore()
            tracker = DisagreementTracker(store)
            with patch("keanu.detect.engine.detect_emotion", return_value=[]):
                d = tracker.record("test topic", "human says", "ai says")
                result = tracker.resolve(d.id, "ai", resolved_by="drew")
            assert result is True
            assert len(store.memories) == 2  # original + resolution lesson
            lesson = store.memories[1]
            assert lesson["memory_type"] == "lesson"
            assert "grievance-resolved" in lesson["tags"]

    def test_tracker_stats_empty(self, tmp_path):
        with patch("keanu.memory.memberberry.MEMBERBERRY_DIR", tmp_path), \
             patch("keanu.memory.memberberry.MEMORIES_FILE", tmp_path / "memories.json"), \
             patch("keanu.memory.memberberry.PLANS_FILE", tmp_path / "plans.json"), \
             patch("keanu.memory.memberberry.CONFIG_FILE", tmp_path / "config.json"):
            store = MemberberryStore()
            tracker = DisagreementTracker(store)
            s = tracker.stats()
            assert s["total"] == 0
            assert s["alerts"] == []


class TestBridge:
    def test_recall_via_openpaw_success(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "results": [
                {"score": 0.85, "path": "drew/2026-02.jsonl", "snippet": "[goal]\nship v1", "startLine": 1, "endLine": 1}
            ]
        })
        with patch("keanu.memory.bridge.subprocess.run", return_value=mock_result):
            results = recall_via_openpaw("ship")
        assert len(results) == 1
        assert results[0]["score"] == 0.85

    def test_recall_via_openpaw_failure(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("keanu.memory.bridge.subprocess.run", return_value=mock_result):
            results = recall_via_openpaw("ship")
        assert results == []

    def test_recall_via_openpaw_not_found(self):
        with patch("keanu.memory.bridge.subprocess.run", side_effect=FileNotFoundError):
            results = recall_via_openpaw("ship")
        assert results == []

    def test_openpaw_available_true(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("keanu.memory.bridge.subprocess.run", return_value=mock_result):
            assert openpaw_available() is True

    def test_openpaw_available_false(self):
        with patch("keanu.memory.bridge.subprocess.run", side_effect=FileNotFoundError):
            assert openpaw_available() is False

    def test_recall_fallback_to_local(self, tmp_path):
        with patch("keanu.memory.memberberry.MEMBERBERRY_DIR", tmp_path), \
             patch("keanu.memory.memberberry.MEMORIES_FILE", tmp_path / "memories.json"), \
             patch("keanu.memory.memberberry.PLANS_FILE", tmp_path / "plans.json"), \
             patch("keanu.memory.memberberry.CONFIG_FILE", tmp_path / "config.json"):
            store = MemberberryStore()
            store.remember(Memory(content="ship v1", memory_type="goal", tags=["build"]))
            with patch("keanu.memory.bridge.subprocess.run", side_effect=FileNotFoundError):
                results = store.recall(query="ship")
            assert len(results) == 1
            assert results[0]["content"] == "ship v1"
