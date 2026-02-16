"""project.py - auto-detect project type, parse manifests, know the commands.

the agent should know: what kind of project is this? how do I run tests?
how do I build? what's the entry point? this module figures that out
by reading the files that are already there.

in the world: reading the map before walking the territory.
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ProjectModel:
    """everything the agent needs to know about a project."""
    root: str = ""
    kind: str = ""              # python, node, go, rust, unknown
    name: str = ""              # project name from manifest
    version: str = ""           # project version
    entry_points: list = field(default_factory=list)
    test_command: str = ""      # how to run tests
    build_command: str = ""     # how to build
    lint_command: str = ""      # how to lint
    format_command: str = ""    # how to format
    manifest: str = ""          # path to the manifest file
    dependencies: list = field(default_factory=list)
    dev_dependencies: list = field(default_factory=list)
    ci_configs: list = field(default_factory=list)
    extras: dict = field(default_factory=dict)

    def summary(self) -> str:
        """one-line summary for the agent."""
        parts = [f"{self.kind} project"]
        if self.name:
            parts = [f"{self.name} ({self.kind})"]
        if self.test_command:
            parts.append(f"test: {self.test_command}")
        if self.build_command:
            parts.append(f"build: {self.build_command}")
        return " | ".join(parts)


def detect(root: str = ".") -> ProjectModel:
    """auto-detect project type and parse its manifest.

    checks for pyproject.toml, package.json, go.mod, Cargo.toml.
    fills in test/build/lint commands from what it finds.
    """
    root_path = Path(root).resolve()
    model = ProjectModel(root=str(root_path))

    # detect CI configs
    model.ci_configs = _detect_ci(root_path)

    # try each detector in order
    for detector in [
        _detect_python,
        _detect_node,
        _detect_go,
        _detect_rust,
    ]:
        if detector(root_path, model):
            return model

    model.kind = "unknown"
    return model


# ============================================================
# PYTHON
# ============================================================

def _detect_python(root: Path, model: ProjectModel) -> bool:
    """detect Python project from pyproject.toml, setup.py, setup.cfg."""
    pyproject = root / "pyproject.toml"
    setup_py = root / "setup.py"
    setup_cfg = root / "setup.cfg"

    if not (pyproject.exists() or setup_py.exists() or setup_cfg.exists()):
        return False

    model.kind = "python"

    if pyproject.exists():
        model.manifest = str(pyproject)
        _parse_pyproject(pyproject, model)

    # detect test command
    if (root / "tox.ini").exists():
        model.test_command = "tox"
    elif (root / "Makefile").exists() and _makefile_has_target(root / "Makefile", "test"):
        model.test_command = "make test"
    elif (root / "pytest.ini").exists() or (root / "pyproject.toml").exists():
        model.test_command = "pytest"
    else:
        model.test_command = "python -m pytest"

    # detect build command
    if (root / "Makefile").exists() and _makefile_has_target(root / "Makefile", "build"):
        model.build_command = "make build"
    elif pyproject.exists():
        model.build_command = "python -m build"

    # detect lint/format
    if _has_dep(model, "ruff"):
        model.lint_command = "ruff check ."
        model.format_command = "ruff format ."
    elif _has_dep(model, "flake8"):
        model.lint_command = "flake8 ."
    if _has_dep(model, "black"):
        model.format_command = "black ."

    # detect entry points
    if (root / "src").is_dir():
        for pkg in (root / "src").iterdir():
            if pkg.is_dir() and (pkg / "__init__.py").exists():
                cli = pkg / "cli.py"
                main = pkg / "__main__.py"
                if cli.exists():
                    model.entry_points.append(str(cli.relative_to(root)))
                if main.exists():
                    model.entry_points.append(str(main.relative_to(root)))

    return True


def _parse_pyproject(path: Path, model: ProjectModel):
    """parse pyproject.toml for project metadata."""
    try:
        text = path.read_text()
    except OSError:
        return

    # basic TOML parsing without a library (just the common fields)
    # only grab name/version from [project] or [package] sections
    in_project = False
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project = stripped in ("[project]", "[package]")
            continue
        if in_project:
            if stripped.startswith("name") and "=" in stripped:
                model.name = _extract_toml_value(stripped)
            elif stripped.startswith("version") and "=" in stripped:
                model.version = _extract_toml_value(stripped)

    # extract dependencies
    in_deps = False
    in_dev = False
    in_array = False
    current_section = ""
    dep_sections = {"[project.dependencies]", "[project]"}
    dev_sections = {"[dependency-groups]", "[project.optional-dependencies]"}

    for line in text.split("\n"):
        stripped = line.strip()

        # track TOML section headers
        if stripped.startswith("[") and stripped.endswith("]"):
            current_section = stripped
            in_deps = current_section in dep_sections
            in_dev = any(s in current_section for s in dev_sections)
            in_array = False
            continue

        # inline array start (e.g. dependencies = [)
        if current_section == "[project]" and stripped.startswith("dependencies") and "= [" in stripped:
            in_deps = True
            in_array = True
            # check if deps are on the same line
            if stripped.endswith("]"):
                in_array = False
                in_deps = False
            continue

        # dev deps inline array (e.g. dev = [)
        if in_dev and "= [" in stripped:
            in_array = True
            if stripped.endswith("]"):
                in_array = False
            continue

        # end of inline array
        if in_array and stripped == "]":
            in_array = False
            if current_section == "[project]":
                in_deps = False
            continue

        # only parse quoted strings inside known dep sections or arrays
        if stripped.startswith('"') and (in_deps and in_array or
                                         current_section == "[project.dependencies]" or
                                         in_dev and in_array):
            dep = stripped.strip('",').split(">=")[0].split("==")[0].split("<")[0].strip()
            if dep and "::" not in dep:  # skip classifiers
                if in_dev:
                    model.dev_dependencies.append(dep)
                else:
                    model.dependencies.append(dep)


# ============================================================
# NODE
# ============================================================

def _detect_node(root: Path, model: ProjectModel) -> bool:
    """detect Node.js project from package.json."""
    pkg_json = root / "package.json"
    if not pkg_json.exists():
        return False

    model.kind = "node"
    model.manifest = str(pkg_json)

    try:
        import json
        data = json.loads(pkg_json.read_text())
    except (json.JSONDecodeError, OSError):
        return True

    model.name = data.get("name", "")
    model.version = data.get("version", "")

    scripts = data.get("scripts", {})
    model.test_command = f"npm test" if "test" in scripts else ""
    model.build_command = f"npm run build" if "build" in scripts else ""
    model.lint_command = f"npm run lint" if "lint" in scripts else ""
    model.format_command = f"npm run format" if "format" in scripts else ""

    deps = data.get("dependencies", {})
    dev_deps = data.get("devDependencies", {})
    model.dependencies = list(deps.keys())
    model.dev_dependencies = list(dev_deps.keys())

    # entry points
    if data.get("main"):
        model.entry_points.append(data["main"])
    if data.get("bin"):
        if isinstance(data["bin"], str):
            model.entry_points.append(data["bin"])
        elif isinstance(data["bin"], dict):
            model.entry_points.extend(data["bin"].values())

    return True


# ============================================================
# GO
# ============================================================

def _detect_go(root: Path, model: ProjectModel) -> bool:
    """detect Go project from go.mod."""
    go_mod = root / "go.mod"
    if not go_mod.exists():
        return False

    model.kind = "go"
    model.manifest = str(go_mod)
    model.test_command = "go test ./..."
    model.build_command = "go build ./..."
    model.lint_command = "golangci-lint run"
    model.format_command = "gofmt -w ."

    try:
        text = go_mod.read_text()
        for line in text.split("\n"):
            if line.startswith("module "):
                model.name = line.split("module ")[1].strip()
                break
    except OSError:
        pass

    # entry points: look for main.go
    for main_go in root.rglob("main.go"):
        model.entry_points.append(str(main_go.relative_to(root)))

    return True


# ============================================================
# RUST
# ============================================================

def _detect_rust(root: Path, model: ProjectModel) -> bool:
    """detect Rust project from Cargo.toml."""
    cargo = root / "Cargo.toml"
    if not cargo.exists():
        return False

    model.kind = "rust"
    model.manifest = str(cargo)
    model.test_command = "cargo test"
    model.build_command = "cargo build"
    model.lint_command = "cargo clippy"
    model.format_command = "cargo fmt"

    try:
        text = cargo.read_text()
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("name") and "=" in line:
                model.name = _extract_toml_value(line)
            elif line.startswith("version") and "=" in line:
                model.version = _extract_toml_value(line)
    except OSError:
        pass

    if (root / "src" / "main.rs").exists():
        model.entry_points.append("src/main.rs")

    return True


# ============================================================
# CI DETECTION
# ============================================================

def _detect_ci(root: Path) -> list[str]:
    """find CI/CD config files."""
    ci_files = []
    checks = [
        ".github/workflows",
        ".gitlab-ci.yml",
        "Jenkinsfile",
        ".circleci/config.yml",
        ".travis.yml",
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "Makefile",
        "tox.ini",
        ".pre-commit-config.yaml",
    ]
    for check in checks:
        path = root / check
        if path.exists():
            if path.is_dir():
                for f in path.iterdir():
                    ci_files.append(str(f.relative_to(root)))
            else:
                ci_files.append(check)
    return ci_files


# ============================================================
# HELPERS
# ============================================================

def _extract_toml_value(line: str) -> str:
    """extract a simple string value from a TOML line."""
    if "=" not in line:
        return ""
    value = line.split("=", 1)[1].strip().strip('"').strip("'")
    return value


def _makefile_has_target(makefile: Path, target: str) -> bool:
    """check if a Makefile has a specific target."""
    try:
        text = makefile.read_text()
        return f"\n{target}:" in text or text.startswith(f"{target}:")
    except OSError:
        return False


def _has_dep(model: ProjectModel, name: str) -> bool:
    """check if a dependency is in the project."""
    all_deps = model.dependencies + model.dev_dependencies
    return any(name in d for d in all_deps)
