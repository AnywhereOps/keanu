"""packaging.py - packaging and distribution helpers.

version management, build validation, install script generation.
checks that the package is ready for distribution.

in the world: the shipping crate. makes sure everything fits.
"""

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PackageCheck:
    """a single packaging check result."""
    name: str
    passed: bool
    message: str
    severity: str = "error"  # error, warning, info


@dataclass
class PackageReport:
    """full packaging validation report."""
    checks: list[PackageCheck] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks if c.severity == "error")

    @property
    def errors(self) -> list[PackageCheck]:
        return [c for c in self.checks if not c.passed and c.severity == "error"]

    @property
    def warnings(self) -> list[PackageCheck]:
        return [c for c in self.checks if not c.passed and c.severity == "warning"]

    def summary(self) -> str:
        passed = sum(1 for c in self.checks if c.passed)
        total = len(self.checks)
        errors = len(self.errors)
        warnings = len(self.warnings)
        return f"{passed}/{total} checks passed, {errors} errors, {warnings} warnings"


# ============================================================
# VERSION MANAGEMENT
# ============================================================

def get_version(root: str = ".") -> str:
    """get the current version from pyproject.toml or setup files."""
    root_path = Path(root)

    # try pyproject.toml
    pyproject = root_path / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text()
        match = re.search(r'version\s*=\s*"([^"]+)"', content)
        if match:
            return match.group(1)

    # try setup.cfg
    setup_cfg = root_path / "setup.cfg"
    if setup_cfg.exists():
        content = setup_cfg.read_text()
        match = re.search(r'version\s*=\s*(\S+)', content)
        if match:
            return match.group(1)

    # try __version__ in package init
    for init in root_path.rglob("__init__.py"):
        try:
            content = init.read_text()
            match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)
        except OSError:
            pass

    # try package.json
    pkg_json = root_path / "package.json"
    if pkg_json.exists():
        import json
        try:
            data = json.loads(pkg_json.read_text())
            return data.get("version", "0.0.0")
        except (json.JSONDecodeError, OSError):
            pass

    return "0.0.0"


def bump_version(current: str, part: str = "patch") -> str:
    """bump a semver version string."""
    match = re.match(r'(\d+)\.(\d+)\.(\d+)(.*)', current)
    if not match:
        return current

    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))

    if part == "major":
        return f"{major + 1}.0.0"
    elif part == "minor":
        return f"{major}.{minor + 1}.0"
    elif part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    return current


# ============================================================
# PACKAGING VALIDATION
# ============================================================

def validate_package(root: str = ".") -> PackageReport:
    """validate that a package is ready for distribution."""
    root_path = Path(root)
    report = PackageReport()

    # check for pyproject.toml or setup.py
    has_pyproject = (root_path / "pyproject.toml").exists()
    has_setup = (root_path / "setup.py").exists()
    has_setup_cfg = (root_path / "setup.cfg").exists()
    has_pkg_json = (root_path / "package.json").exists()

    report.checks.append(PackageCheck(
        name="manifest",
        passed=has_pyproject or has_setup or has_setup_cfg or has_pkg_json,
        message="found" if any([has_pyproject, has_setup, has_setup_cfg, has_pkg_json]) else "no manifest file",
    ))

    # check version
    version = get_version(root)
    report.checks.append(PackageCheck(
        name="version",
        passed=version != "0.0.0",
        message=f"v{version}" if version != "0.0.0" else "no version found",
    ))

    # check README
    readme_exists = any((root_path / name).exists() for name in ["README.md", "README.rst", "README.txt", "README"])
    report.checks.append(PackageCheck(
        name="readme",
        passed=readme_exists,
        message="found" if readme_exists else "no README",
        severity="warning",
    ))

    # check LICENSE
    license_exists = any((root_path / name).exists() for name in ["LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"])
    report.checks.append(PackageCheck(
        name="license",
        passed=license_exists,
        message="found" if license_exists else "no LICENSE",
        severity="warning",
    ))

    # check .gitignore
    gitignore = root_path / ".gitignore"
    report.checks.append(PackageCheck(
        name="gitignore",
        passed=gitignore.exists(),
        message="found" if gitignore.exists() else "no .gitignore",
        severity="warning",
    ))

    # check tests exist
    has_tests = any((root_path / d).is_dir() for d in ["tests", "test", "spec"])
    report.checks.append(PackageCheck(
        name="tests",
        passed=has_tests,
        message="found" if has_tests else "no test directory",
        severity="warning",
    ))

    # Python-specific checks
    if has_pyproject:
        _check_pyproject(root_path, report)

    return report


def _check_pyproject(root_path: Path, report: PackageReport):
    """check pyproject.toml for common issues."""
    try:
        content = (root_path / "pyproject.toml").read_text()
    except OSError:
        return

    # check for required fields
    has_name = "name" in content
    has_description = "description" in content
    has_build_system = "[build-system]" in content

    report.checks.append(PackageCheck(
        name="pyproject.name",
        passed=has_name,
        message="found" if has_name else "missing name in pyproject.toml",
    ))
    report.checks.append(PackageCheck(
        name="pyproject.description",
        passed=has_description,
        message="found" if has_description else "missing description",
        severity="warning",
    ))
    report.checks.append(PackageCheck(
        name="pyproject.build-system",
        passed=has_build_system,
        message="found" if has_build_system else "missing [build-system]",
    ))


# ============================================================
# INSTALL SCRIPT
# ============================================================

def generate_install_script(root: str = ".", name: str = "") -> str:
    """generate a one-line install script for the package."""
    version = get_version(root)
    pkg_name = name or _detect_package_name(root)

    lines = [
        "#!/bin/bash",
        f"# Install {pkg_name}",
        "set -e",
        "",
    ]

    root_path = Path(root)
    if (root_path / "pyproject.toml").exists():
        lines.extend([
            "# Check Python version",
            'python3 -c "import sys; assert sys.version_info >= (3, 10), \'Python 3.10+ required\'"',
            "",
            f"# Install {pkg_name}",
            f"pip install {pkg_name}" if version != "0.0.0" else "pip install -e .",
            "",
        ])
    elif (root_path / "package.json").exists():
        lines.extend([
            "# Check Node.js",
            "node --version || { echo 'Node.js required'; exit 1; }",
            "",
            f"# Install {pkg_name}",
            f"npm install {pkg_name}" if version != "0.0.0" else "npm install",
            "",
        ])
    else:
        lines.append("echo 'Unknown package type'")

    lines.append(f'echo "Installed {pkg_name} v{version}"')
    return "\n".join(lines) + "\n"


def _detect_package_name(root: str) -> str:
    """detect the package name from project files."""
    root_path = Path(root)

    pyproject = root_path / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text()
        match = re.search(r'name\s*=\s*"([^"]+)"', content)
        if match:
            return match.group(1)

    pkg_json = root_path / "package.json"
    if pkg_json.exists():
        import json
        try:
            return json.loads(pkg_json.read_text()).get("name", "unknown")
        except (json.JSONDecodeError, OSError):
            pass

    return root_path.name


# ============================================================
# BUILD HELPERS
# ============================================================

def check_build(root: str = ".") -> dict:
    """check if the package builds successfully."""
    try:
        result = subprocess.run(
            ["python3", "-m", "build", "--no-isolation"],
            capture_output=True, text=True, timeout=120,
            cwd=root,
        )
        return {
            "success": result.returncode == 0,
            "output": result.stdout[-500:],
            "error": result.stderr[-500:] if result.returncode != 0 else "",
        }
    except FileNotFoundError:
        return {"success": False, "error": "python3 -m build not available (pip install build)"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "build timed out"}


def list_dist_files(root: str = ".") -> list[str]:
    """list built distribution files."""
    dist = Path(root) / "dist"
    if not dist.is_dir():
        return []
    return sorted(str(f) for f in dist.iterdir() if f.suffix in (".whl", ".tar.gz", ".zip"))
