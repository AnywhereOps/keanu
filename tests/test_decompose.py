"""tests for task decomposition."""

from keanu.hero.decompose import (
    is_complex, decompose_simple, decompose, Decomposition, Subtask,
)


class TestIsComplex:

    def test_simple_task(self):
        assert not is_complex("fix the bug in login.py")

    def test_numbered_steps(self):
        assert is_complex("1. read the file 2. fix the bug 3. run tests")

    def test_bullet_points(self):
        assert is_complex("- fix the bug\n- add tests\n- update docs")

    def test_and_then(self):
        assert is_complex("first, read the file and then fix the bug and then run tests")

    def test_multiple_sentences(self):
        assert is_complex("Read the file. Find the bug. Fix it. Run the tests.")

    def test_multiple_files(self):
        assert is_complex("update main.py and test_main.py and config.json to handle the new feature")

    def test_long_task(self):
        assert is_complex("x " * 200)


class TestDecomposeSimple:

    def test_numbered_steps(self):
        task = "1. read foo.py\n2. fix the bug\n3. run tests"
        result = decompose_simple(task)
        assert result.is_complex
        assert len(result.subtasks) == 3
        assert "read foo.py" in result.subtasks[0].action

    def test_bullet_points(self):
        task = "- add error handling\n- write tests\n- update docs"
        result = decompose_simple(task)
        assert result.is_complex
        assert len(result.subtasks) == 3

    def test_and_then_splitting(self):
        task = "first, read the config and then update the parser and then test it"
        result = decompose_simple(task)
        assert result.is_complex
        assert len(result.subtasks) >= 2

    def test_sentence_splitting(self):
        task = "Read the file. Find the broken function. Fix the return type. Add a test."
        result = decompose_simple(task)
        assert result.is_complex
        assert len(result.subtasks) >= 3

    def test_simple_task_not_decomposed(self):
        task = "fix the typo"
        result = decompose_simple(task)
        assert not result.is_complex
        assert len(result.subtasks) == 0


class TestDecompose:

    def test_simple_task(self):
        result = decompose("fix bug")
        assert not result.is_complex

    def test_complex_task(self):
        result = decompose("1. read file\n2. fix bug\n3. test")
        assert result.is_complex
        assert result.total >= 3

    def test_progress(self):
        d = Decomposition(
            original="test",
            subtasks=[
                Subtask(action="a", status="done"),
                Subtask(action="b", status="done"),
                Subtask(action="c", status="pending"),
            ],
            is_complex=True,
        )
        assert d.progress == "2/3"
        assert d.done == 2
        assert d.failed == 0


class TestSubtask:

    def test_defaults(self):
        s = Subtask(action="do the thing")
        assert s.status == "pending"
        assert s.phase == ""
        assert s.depends_on == ""
