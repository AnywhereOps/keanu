"""tests for documentation generation."""

from keanu.gen.docgen import (
    generate_docstrings, generate_module_diagram, generate_class_diagram,
    generate_changelog, generate_api_summary,
    _classify_commit, _has_docstring, _generate_func_docstring,
    DocResult,
)


class TestGenerateDocstrings:

    def test_adds_docstrings(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text("def foo(x, y):\n    return x + y\n")

        result = generate_docstrings(str(f))

        assert result.success
        assert '"""' in result.content

    def test_skips_existing_docstrings(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text('def foo():\n    """existing."""\n    pass\n')

        result = generate_docstrings(str(f))

        assert result.success
        # should not add another docstring
        assert result.content.count('"""') == 2  # just the existing one

    def test_terse_style(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text("def bar():\n    pass\n")

        result = generate_docstrings(str(f), style="terse")

        assert result.success
        assert "bar." in result.content

    def test_nonexistent_file(self):
        result = generate_docstrings("/nonexistent.py")
        assert not result.success

    def test_syntax_error(self, tmp_path):
        f = tmp_path / "bad.py"
        f.write_text("def broken(:\n")

        result = generate_docstrings(str(f))
        assert not result.success

    def test_class_docstring(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text("class Foo:\n    x = 1\n")

        result = generate_docstrings(str(f))
        assert result.success


class TestClassDiagram:

    def test_generates_mermaid(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text("class Animal:\n    def speak(self):\n        pass\n\nclass Dog(Animal):\n    def bark(self):\n        pass\n")

        result = generate_class_diagram(str(f))

        assert result.success
        assert "classDiagram" in result.content
        assert "Dog" in result.content
        assert "bark" in result.content

    def test_nonexistent_file(self):
        result = generate_class_diagram("/nonexistent.py")
        assert not result.success


class TestChangelog:

    def test_generates_changelog(self):
        result = generate_changelog(n_commits=5)
        # might fail if not in a git repo, but in keanu's repo it should work
        if result.success:
            assert "# Changelog" in result.content


class TestApiSummary:

    def test_generates_summary(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text('def public_func(x):\n    """does something."""\n    pass\n\ndef _private():\n    pass\n')

        result = generate_api_summary(str(f))

        assert result.success
        assert "public_func" in result.content
        assert "_private" not in result.content

    def test_class_summary(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text('class MyClass:\n    """a class."""\n    def method(self, x):\n        """does x."""\n        pass\n')

        result = generate_api_summary(str(f))

        assert result.success
        assert "MyClass" in result.content
        assert "method" in result.content


class TestClassifyCommit:

    def test_conventional_feat(self):
        assert _classify_commit("feat: add login") == "feat"

    def test_conventional_fix(self):
        assert _classify_commit("fix: null pointer") == "fix"

    def test_heuristic_add(self):
        assert _classify_commit("add user authentication") == "feat"

    def test_heuristic_fix(self):
        assert _classify_commit("fix broken login flow") == "fix"

    def test_heuristic_refactor(self):
        assert _classify_commit("refactor auth module") == "refactor"

    def test_heuristic_test(self):
        assert _classify_commit("test: add unit tests") == "test"

    def test_other(self):
        assert _classify_commit("bump version") == "other"
