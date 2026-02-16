"""tests for multi-agent coordination."""

from unittest.mock import patch, MagicMock

from keanu.hero.coordinate import (
    Pipeline, AgentRole, AgentTask, PipelineResult,
    plan_build_verify, parallel_investigate,
    detect_disagreement, Disagreement,
)


class TestAgentTask:

    def test_creates_id(self):
        t = AgentTask(role=AgentRole.CRAFT, task="build something")
        assert t.id.startswith("craft_")
        assert t.status == "pending"

    def test_custom_id(self):
        t = AgentTask(role=AgentRole.CRAFT, task="x", id="custom")
        assert t.id == "custom"


class TestPipeline:

    def _mock_dispatch(self, role, task, legend, model, store):
        return {"ok": True, "answer": f"done: {task[:30]}", "steps": 1, "extras": {}, "error": ""}

    def test_single_task(self):
        with patch("keanu.hero.coordinate._dispatch_to_agent", side_effect=self._mock_dispatch):
            p = Pipeline()
            p.add(AgentRole.CRAFT, "build a thing")
            result = p.run()
        assert result.success
        assert len(result.completed) == 1

    def test_sequential_tasks(self):
        with patch("keanu.hero.coordinate._dispatch_to_agent", side_effect=self._mock_dispatch):
            p = Pipeline()
            id1 = p.add(AgentRole.ARCHITECT, "plan", task_id="plan")
            p.add(AgentRole.CRAFT, "build", depends_on=[id1], task_id="build")
            result = p.run()
        assert result.success
        assert len(result.completed) == 2
        # plan should finish before build
        plan = next(t for t in result.tasks if t.id == "plan")
        build = next(t for t in result.tasks if t.id == "build")
        assert plan.finished_at <= build.started_at

    def test_parallel_tasks(self):
        with patch("keanu.hero.coordinate._dispatch_to_agent", side_effect=self._mock_dispatch):
            p = Pipeline(max_workers=3)
            p.add(AgentRole.EXPLORE, "question 1", task_id="q1")
            p.add(AgentRole.EXPLORE, "question 2", task_id="q2")
            p.add(AgentRole.EXPLORE, "question 3", task_id="q3")
            result = p.run()
        assert result.success
        assert len(result.completed) == 3

    def test_failed_task(self):
        def failing_dispatch(role, task, legend, model, store):
            if "fail" in task:
                raise ValueError("intentional failure")
            return {"ok": True, "answer": "done", "steps": 1, "extras": {}, "error": ""}

        with patch("keanu.hero.coordinate._dispatch_to_agent", side_effect=failing_dispatch):
            p = Pipeline()
            p.add(AgentRole.CRAFT, "fail this")
            result = p.run()
        assert not result.success
        assert len(result.failed) == 1

    def test_deadlock_detection(self):
        with patch("keanu.hero.coordinate._dispatch_to_agent", side_effect=self._mock_dispatch):
            p = Pipeline()
            p.add(AgentRole.CRAFT, "a", depends_on=["b"], task_id="a")
            p.add(AgentRole.CRAFT, "b", depends_on=["a"], task_id="b")
            result = p.run()
        assert not result.success
        assert any("deadlock" in e for e in result.errors)

    def test_context_sharing(self):
        call_log = []
        def tracking_dispatch(role, task, legend, model, store):
            call_log.append(task)
            return {"ok": True, "answer": "result from agent", "steps": 1, "extras": {}, "error": ""}

        with patch("keanu.hero.coordinate._dispatch_to_agent", side_effect=tracking_dispatch):
            p = Pipeline()
            id1 = p.add(AgentRole.EXPLORE, "investigate", task_id="explore")
            p.add(AgentRole.CRAFT, "build", depends_on=[id1], task_id="build")
            result = p.run()

        assert result.success
        # second task should have context from first
        assert any("Context from previous agents" in call for call in call_log)


class TestPipelineResult:

    def test_completed(self):
        tasks = [
            AgentTask(role=AgentRole.CRAFT, task="a", status="done"),
            AgentTask(role=AgentRole.CRAFT, task="b", status="failed"),
        ]
        r = PipelineResult(success=False, tasks=tasks)
        assert len(r.completed) == 1
        assert len(r.failed) == 1


class TestCommonPipelines:

    def _mock_dispatch(self, role, task, legend, model, store):
        return {"ok": True, "answer": "done", "steps": 1, "extras": {}, "error": ""}

    def test_plan_build_verify(self):
        with patch("keanu.hero.coordinate._dispatch_to_agent", side_effect=self._mock_dispatch):
            result = plan_build_verify("build auth")
        assert result.success
        assert len(result.completed) == 3

    def test_parallel_investigate(self):
        with patch("keanu.hero.coordinate._dispatch_to_agent", side_effect=self._mock_dispatch):
            result = parallel_investigate(["q1", "q2", "q3"])
        assert result.success
        assert len(result.completed) == 3


class TestDisagreement:

    def test_detects_contradiction(self):
        results = {
            "craft": {"answer": "Yes, we should use Redis"},
            "prove": {"answer": "No, we should not use Redis"},
        }
        d = detect_disagreement(results)
        assert d is not None
        assert len(d.positions) == 2

    def test_no_disagreement(self):
        results = {
            "craft": {"answer": "Use Redis for caching"},
            "prove": {"answer": "Redis works well for this use case"},
        }
        d = detect_disagreement(results)
        assert d is None

    def test_single_result(self):
        results = {"craft": {"answer": "done"}}
        d = detect_disagreement(results)
        assert d is None

    def test_empty_answers(self):
        results = {"craft": {"answer": ""}, "prove": {"answer": ""}}
        d = detect_disagreement(results)
        assert d is None
