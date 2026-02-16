"""tests for project scaffolding."""

from keanu.gen.scaffold import (
    python_package, cli_tool, web_api, library,
    scaffold, list_templates,
    ScaffoldFile, ScaffoldResult,
)


class TestPythonPackage:

    def test_creates_files(self):
        files = python_package("myapp", "a cool app")
        paths = [f.path for f in files]
        assert "pyproject.toml" in paths
        assert "src/myapp/__init__.py" in paths
        assert "src/myapp/main.py" in paths
        assert "tests/test_myapp.py" in paths
        assert ".gitignore" in paths
        assert "README.md" in paths

    def test_version_in_init(self):
        files = python_package("myapp")
        init = next(f for f in files if f.path.endswith("__init__.py"))
        assert "__version__" in init.content

    def test_sanitizes_name(self):
        files = python_package("my-cool-app")
        init = next(f for f in files if f.path.endswith("__init__.py"))
        assert "my_cool_app" in init.path


class TestCliTool:

    def test_has_argparse(self):
        files = cli_tool("mytool", "a tool")
        main = next(f for f in files if f.path.endswith("main.py"))
        assert "argparse" in main.content

    def test_has_scripts_entry(self):
        files = cli_tool("mytool")
        pyproject = next(f for f in files if f.path == "pyproject.toml")
        assert "[project.scripts]" in pyproject.content
        assert "mytool" in pyproject.content


class TestWebApi:

    def test_flask(self):
        files = web_api("myapi", framework="flask")
        main = next(f for f in files if f.path.endswith("main.py"))
        assert "Flask" in main.content
        assert "/health" in main.content

    def test_fastapi(self):
        files = web_api("myapi", framework="fastapi")
        main = next(f for f in files if f.path.endswith("main.py"))
        assert "FastAPI" in main.content

    def test_has_dockerfile(self):
        files = web_api("myapi")
        paths = [f.path for f in files]
        assert "Dockerfile" in paths


class TestLibrary:

    def test_has_docs(self):
        files = library("mylib", "a library")
        paths = [f.path for f in files]
        assert "docs/index.md" in paths
        assert "LICENSE" in paths
        assert "CHANGELOG.md" in paths


class TestScaffold:

    def test_dry_run(self, tmp_path):
        result = scaffold("package", "testapp", str(tmp_path), dry_run=True)
        assert len(result.files_created) >= 5
        # dry run should not create files
        assert not (tmp_path / "pyproject.toml").exists()

    def test_creates_files(self, tmp_path):
        result = scaffold("package", "testapp", str(tmp_path))
        assert (tmp_path / "pyproject.toml").exists()
        assert (tmp_path / "src" / "testapp" / "__init__.py").exists()
        assert (tmp_path / "tests" / "test_testapp.py").exists()

    def test_cli_template(self, tmp_path):
        result = scaffold("cli", "mycli", str(tmp_path))
        assert (tmp_path / "src" / "mycli" / "main.py").exists()
        content = (tmp_path / "src" / "mycli" / "main.py").read_text()
        assert "argparse" in content

    def test_unknown_template(self, tmp_path):
        try:
            scaffold("nonexistent", "x", str(tmp_path))
            assert False, "should raise"
        except ValueError as e:
            assert "unknown template" in str(e)

    def test_result_fields(self, tmp_path):
        result = scaffold("package", "myapp", str(tmp_path))
        assert result.template == "package"
        assert result.name == "myapp"
        assert len(result.files_created) >= 5


class TestListTemplates:

    def test_returns_templates(self):
        templates = list_templates()
        assert len(templates) >= 4
        names = [t["name"] for t in templates]
        assert "package" in names
        assert "cli" in names
        assert "api" in names
        assert "library" in names
