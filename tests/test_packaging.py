"""tests for packaging and distribution."""

from keanu.abilities.world.packaging import (
    get_version, bump_version, validate_package,
    generate_install_script, _detect_package_name,
    PackageCheck, PackageReport,
)


class TestGetVersion:

    def test_from_pyproject(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\nversion = "1.2.3"\n')
        assert get_version(str(tmp_path)) == "1.2.3"

    def test_from_setup_cfg(self, tmp_path):
        (tmp_path / "setup.cfg").write_text("[metadata]\nversion = 2.0.0\n")
        assert get_version(str(tmp_path)) == "2.0.0"

    def test_from_init(self, tmp_path):
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text('__version__ = "3.1.4"\n')
        assert get_version(str(tmp_path)) == "3.1.4"

    def test_from_package_json(self, tmp_path):
        (tmp_path / "package.json").write_text('{"name": "test", "version": "4.0.0"}')
        assert get_version(str(tmp_path)) == "4.0.0"

    def test_fallback(self, tmp_path):
        assert get_version(str(tmp_path)) == "0.0.0"


class TestBumpVersion:

    def test_patch(self):
        assert bump_version("1.2.3", "patch") == "1.2.4"

    def test_minor(self):
        assert bump_version("1.2.3", "minor") == "1.3.0"

    def test_major(self):
        assert bump_version("1.2.3", "major") == "2.0.0"

    def test_invalid(self):
        assert bump_version("invalid", "patch") == "invalid"


class TestValidatePackage:

    def test_valid_python_project(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "1.0.0"\ndescription = "a test"\n'
            '[build-system]\nrequires = ["hatchling"]\n'
        )
        (tmp_path / "README.md").write_text("# Test\n")
        (tmp_path / "LICENSE").write_text("MIT\n")
        (tmp_path / ".gitignore").write_text("*.pyc\n")
        (tmp_path / "tests").mkdir()

        report = validate_package(str(tmp_path))
        assert report.passed
        assert len(report.errors) == 0

    def test_empty_project(self, tmp_path):
        report = validate_package(str(tmp_path))
        assert not report.passed

    def test_missing_readme_is_warning(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "1.0.0"\n[build-system]\n')
        report = validate_package(str(tmp_path))
        readme_check = next(c for c in report.checks if c.name == "readme")
        assert not readme_check.passed
        assert readme_check.severity == "warning"


class TestPackageReport:

    def test_summary(self):
        report = PackageReport(checks=[
            PackageCheck(name="a", passed=True, message="ok"),
            PackageCheck(name="b", passed=False, message="fail", severity="error"),
            PackageCheck(name="c", passed=False, message="warn", severity="warning"),
        ])
        assert "1/3" in report.summary()
        assert len(report.errors) == 1
        assert len(report.warnings) == 1

    def test_all_passed(self):
        report = PackageReport(checks=[
            PackageCheck(name="a", passed=True, message="ok"),
        ])
        assert report.passed


class TestGenerateInstallScript:

    def test_python_project(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "myapp"\nversion = "1.0.0"\n')
        script = generate_install_script(str(tmp_path))
        assert "pip install" in script
        assert "myapp" in script

    def test_node_project(self, tmp_path):
        (tmp_path / "package.json").write_text('{"name": "myapp", "version": "1.0.0"}')
        script = generate_install_script(str(tmp_path))
        assert "npm install" in script

    def test_custom_name(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "1.0.0"\n')
        script = generate_install_script(str(tmp_path), name="custom-name")
        assert "custom-name" in script


class TestDetectPackageName:

    def test_from_pyproject(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "coolpkg"\n')
        assert _detect_package_name(str(tmp_path)) == "coolpkg"

    def test_fallback_to_dir_name(self, tmp_path):
        assert _detect_package_name(str(tmp_path)) == tmp_path.name
