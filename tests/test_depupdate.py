"""Tests for depupdate.py - dependency update management."""

import json
import os

from keanu.data.depupdate import (
    Dependency,
    UpdateInfo,
    check_outdated,
    classify_update,
    find_manifest,
    format_update_report,
    generate_update_commands,
    parse_manifest,
    parse_package_json,
    parse_pyproject,
    parse_requirements,
    parse_version,
    pin_versions,
)


class TestParseVersion:
    def test_simple(self):
        assert parse_version("1.2.3") == (1, 2, 3)

    def test_two_part(self):
        assert parse_version("2.1") == (2, 1, 0)

    def test_one_part(self):
        assert parse_version("5") == (5, 0, 0)

    def test_caret_prefix(self):
        assert parse_version("^1.4.2") == (1, 4, 2)

    def test_tilde_prefix(self):
        assert parse_version("~2.0.1") == (2, 0, 1)

    def test_gte_prefix(self):
        assert parse_version(">=3.1.0") == (3, 1, 0)

    def test_garbage(self):
        assert parse_version("latest") == (0, 0, 0)

    def test_empty(self):
        assert parse_version("") == (0, 0, 0)


class TestClassifyUpdate:
    def test_major(self):
        assert classify_update("1.2.3", "2.0.0") == "major"

    def test_minor(self):
        assert classify_update("1.2.3", "1.3.0") == "minor"

    def test_patch(self):
        assert classify_update("1.2.3", "1.2.4") == "patch"

    def test_none_same(self):
        assert classify_update("1.2.3", "1.2.3") == "none"

    def test_none_downgrade(self):
        assert classify_update("2.0.0", "1.9.9") == "none"

    def test_with_prefixes(self):
        assert classify_update(">=1.0.0", "^2.0.0") == "major"


class TestParseRequirements:
    def test_pinned(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("requests==2.28.0\n")
        deps = parse_requirements(str(tmp_path / "requirements.txt"))
        assert len(deps) == 1
        assert deps[0].name == "requests"
        assert deps[0].current_version == "2.28.0"
        assert deps[0].pinned is True

    def test_gte(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("flask>=2.0\n")
        deps = parse_requirements(str(tmp_path / "requirements.txt"))
        assert deps[0].current_version == "2.0"
        assert deps[0].pinned is False

    def test_tilde(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("django~=4.2.0\n")
        deps = parse_requirements(str(tmp_path / "requirements.txt"))
        assert deps[0].current_version == "4.2.0"

    def test_comments_and_blanks(self, tmp_path):
        content = "# this is a comment\n\nrequests==1.0\n  # indented\n\nflask>=2.0\n"
        (tmp_path / "requirements.txt").write_text(content)
        deps = parse_requirements(str(tmp_path / "requirements.txt"))
        assert len(deps) == 2

    def test_inline_comment(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("requests==2.28.0  # http lib\n")
        deps = parse_requirements(str(tmp_path / "requirements.txt"))
        assert deps[0].name == "requests"

    def test_include(self, tmp_path):
        (tmp_path / "base.txt").write_text("requests==2.28.0\n")
        (tmp_path / "requirements.txt").write_text("-r base.txt\nflask>=2.0\n")
        deps = parse_requirements(str(tmp_path / "requirements.txt"))
        assert len(deps) == 2
        names = {d.name for d in deps}
        assert names == {"requests", "flask"}

    def test_source_field(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("click==8.0\n")
        deps = parse_requirements(str(tmp_path / "requirements.txt"))
        assert deps[0].source == "requirements.txt"


class TestParsePyproject:
    def test_dependencies(self, tmp_path):
        toml = '[project]\ndependencies = [\n  "requests>=2.28.0",\n  "click==8.1.0",\n]\n'
        (tmp_path / "pyproject.toml").write_text(toml)
        deps = parse_pyproject(str(tmp_path / "pyproject.toml"))
        assert len(deps) == 2
        assert deps[0].name == "requests"
        assert deps[1].pinned is True

    def test_optional_deps(self, tmp_path):
        toml = (
            "[project]\ndependencies = []\n"
            '[project.optional-dependencies]\ndev = ["pytest>=7.0"]\n'
        )
        (tmp_path / "pyproject.toml").write_text(toml)
        deps = parse_pyproject(str(tmp_path / "pyproject.toml"))
        assert len(deps) == 1
        assert deps[0].dev is True

    def test_source(self, tmp_path):
        toml = '[project]\ndependencies = ["click>=8.0"]\n'
        (tmp_path / "pyproject.toml").write_text(toml)
        deps = parse_pyproject(str(tmp_path / "pyproject.toml"))
        assert deps[0].source == "pyproject.toml"

    def test_extras_stripped(self, tmp_path):
        toml = '[project]\ndependencies = ["mkdocstrings[python]>=1.0"]\n'
        (tmp_path / "pyproject.toml").write_text(toml)
        deps = parse_pyproject(str(tmp_path / "pyproject.toml"))
        assert deps[0].name == "mkdocstrings"


class TestParsePackageJson:
    def test_deps(self, tmp_path):
        data = {"dependencies": {"react": "^18.2.0"}, "devDependencies": {"jest": "~29.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(data))
        deps = parse_package_json(str(tmp_path / "package.json"))
        assert len(deps) == 2
        react = [d for d in deps if d.name == "react"][0]
        jest = [d for d in deps if d.name == "jest"][0]
        assert react.dev is False
        assert jest.dev is True
        assert react.current_version == "18.2.0"
        assert react.source == "package.json"

    def test_pinned_detection(self, tmp_path):
        data = {"dependencies": {"lodash": "4.17.21"}}
        (tmp_path / "package.json").write_text(json.dumps(data))
        deps = parse_package_json(str(tmp_path / "package.json"))
        assert deps[0].pinned is True


class TestFindManifest:
    def test_finds_files(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("")
        (tmp_path / "requirements.txt").write_text("")
        found = find_manifest(str(tmp_path))
        assert len(found) == 2

    def test_empty_dir(self, tmp_path):
        assert find_manifest(str(tmp_path)) == []

    def test_package_json(self, tmp_path):
        (tmp_path / "package.json").write_text("{}")
        found = find_manifest(str(tmp_path))
        assert len(found) == 1
        assert "package.json" in found[0]


class TestParseManifest:
    def test_autodetect_pyproject(self, tmp_path):
        toml = '[project]\ndependencies = ["click>=8.0"]\n'
        p = tmp_path / "pyproject.toml"
        p.write_text(toml)
        deps = parse_manifest(str(p))
        assert deps[0].name == "click"

    def test_autodetect_requirements(self, tmp_path):
        p = tmp_path / "requirements.txt"
        p.write_text("flask==2.0\n")
        deps = parse_manifest(str(p))
        assert deps[0].name == "flask"

    def test_unknown_returns_empty(self, tmp_path):
        p = tmp_path / "Gemfile"
        p.write_text("gem 'rails'\n")
        assert parse_manifest(str(p)) == []


class TestCheckOutdated:
    def test_finds_updates(self):
        deps = [
            Dependency("a", "1.0.0", latest_version="2.0.0", source="requirements.txt"),
            Dependency("b", "1.0.0", latest_version="1.1.0", source="requirements.txt"),
            Dependency("c", "1.0.0", latest_version="1.0.0", source="requirements.txt"),
        ]
        updates = check_outdated(deps)
        assert len(updates) == 2
        types = {u.dependency.name: u.update_type for u in updates}
        assert types["a"] == "major"
        assert types["b"] == "minor"

    def test_breaking_flag(self):
        deps = [Dependency("x", "1.0.0", latest_version="2.0.0", source="requirements.txt")]
        updates = check_outdated(deps)
        assert updates[0].breaking is True

    def test_skips_no_latest(self):
        deps = [Dependency("x", "1.0.0", source="requirements.txt")]
        assert check_outdated(deps) == []


class TestGenerateUpdateCommands:
    def test_pip_commands(self):
        updates = [
            UpdateInfo(Dependency("requests", "2.28", latest_version="2.31", source="requirements.txt"), "minor"),
        ]
        cmds = generate_update_commands(updates)
        assert cmds == ["pip install requests==2.31"]

    def test_npm_commands(self):
        updates = [
            UpdateInfo(Dependency("react", "18.2.0", latest_version="19.0.0", source="package.json"), "major"),
        ]
        cmds = generate_update_commands(updates)
        assert cmds == ["npm install react@19.0.0"]

    def test_npm_dev(self):
        updates = [
            UpdateInfo(Dependency("jest", "29.0", latest_version="30.0", source="package.json", dev=True), "major"),
        ]
        cmds = generate_update_commands(updates)
        assert "--save-dev" in cmds[0]


class TestFormatUpdateReport:
    def test_no_updates(self):
        assert "up to date" in format_update_report([])

    def test_with_updates(self):
        updates = [
            UpdateInfo(
                Dependency("requests", "2.28", latest_version="2.31", source="requirements.txt"),
                "minor",
            ),
            UpdateInfo(
                Dependency("click", "7.0", latest_version="8.0", source="requirements.txt"),
                "major",
                breaking=True,
            ),
        ]
        report = format_update_report(updates)
        assert "requests" in report
        assert "2.28 -> 2.31" in report
        assert "[BREAKING]" in report
        assert "2 update(s)" in report


class TestPinVersions:
    def test_pin(self):
        deps = [
            Dependency("requests", "2.28.0", source="requirements.txt"),
            Dependency("click", "8.1.0", source="requirements.txt"),
        ]
        lines = pin_versions(deps)
        assert lines == ["requests==2.28.0", "click==8.1.0"]

    def test_no_version(self):
        deps = [Dependency("something", "", source="requirements.txt")]
        lines = pin_versions(deps)
        assert lines == ["something"]
