"""tests for context manager."""

from keanu.context import ContextManager, FileContext


class TestFileContext:

    def test_defaults(self):
        fc = FileContext(path="foo.py")
        assert fc.size == 0
        assert not fc.modified


class TestContextManager:

    def test_note_file(self):
        cm = ContextManager()
        cm.note_file("foo.py", content="x = 1\ny = 2\n", turn=1)
        assert "foo.py" in cm.files
        assert cm.files["foo.py"].lines == 3
        assert cm.files["foo.py"].size == 12

    def test_note_modified(self):
        cm = ContextManager()
        cm.note_file("foo.py", content="x = 1")
        cm.note_modified("foo.py")
        assert cm.files["foo.py"].modified

    def test_note_modified_unknown_file(self):
        cm = ContextManager()
        cm.note_modified("unknown.py")  # no crash

    def test_budget_tracking(self):
        cm = ContextManager(token_budget=100)
        cm.note_file("a.py", content="x" * 400)  # ~100 tokens
        assert cm.budget_remaining() == 0.0

    def test_budget_remaining_fresh(self):
        cm = ContextManager(token_budget=1000)
        assert cm.budget_remaining() == 1.0

    def test_is_tight(self):
        cm = ContextManager(token_budget=100)
        assert not cm.is_tight()
        cm.tokens_used = 85
        assert cm.is_tight()

    def test_priority_files_modified_first(self):
        cm = ContextManager()
        cm.note_file("a.py", content="x", turn=1)
        cm.note_file("b.py", content="x", turn=2)
        cm.note_file("c.py", content="x", turn=3)
        cm.note_modified("a.py")
        pf = cm.priority_files()
        assert pf[0] == "a.py"  # modified comes first

    def test_priority_files_recency(self):
        cm = ContextManager()
        cm.note_file("old.py", content="x", turn=1)
        cm.note_file("new.py", content="x", turn=5)
        pf = cm.priority_files()
        assert pf[0] == "new.py"

    def test_priority_files_limit(self):
        cm = ContextManager()
        for i in range(20):
            cm.note_file(f"f{i}.py", content="x", turn=i)
        pf = cm.priority_files(n=5)
        assert len(pf) == 5

    def test_known_files(self):
        cm = ContextManager()
        cm.note_file("b.py")
        cm.note_file("a.py")
        assert cm.known_files() == ["a.py", "b.py"]

    def test_summary(self):
        cm = ContextManager()
        cm.note_file("a.py", content="x")
        cm.note_modified("a.py")
        s = cm.summary()
        assert "1 files read" in s
        assert "1 modified" in s

    def test_context_for_prompt_empty(self):
        cm = ContextManager()
        assert cm.context_for_prompt() == ""

    def test_context_for_prompt_with_files(self):
        cm = ContextManager()
        cm.note_file("a.py", content="x")
        ctx = cm.context_for_prompt()
        assert "[CONTEXT]" in ctx

    def test_context_for_prompt_tight_budget(self):
        cm = ContextManager(token_budget=10)
        cm.note_file("a.py", content="x" * 100)
        ctx = cm.context_for_prompt()
        assert "tight" in ctx.lower()

    def test_context_for_prompt_modified(self):
        cm = ContextManager()
        cm.note_file("edited.py", content="x")
        cm.note_modified("edited.py")
        ctx = cm.context_for_prompt()
        assert "edited.py" in ctx


class TestImportGraph:

    def test_related_to_with_manual_graph(self):
        cm = ContextManager()
        cm.import_graph = {"a.py": ["b.py", "c.py"]}
        cm.reverse_graph = {"b.py": ["a.py"], "c.py": ["a.py"]}
        related = cm.related_to("a.py")
        assert "b.py" in related
        assert "c.py" in related

    def test_importers_of(self):
        cm = ContextManager()
        cm.reverse_graph = {"utils.py": ["main.py", "db.py"]}
        importers = cm.importers_of("utils.py")
        assert "main.py" in importers
        assert "db.py" in importers

    def test_importers_of_empty(self):
        cm = ContextManager()
        assert cm.importers_of("unknown.py") == []

    def test_related_to_empty(self):
        cm = ContextManager()
        assert cm.related_to("x.py") == []
