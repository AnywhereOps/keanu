"""depupdate.py - parse dependency manifests, check for updates, generate reports.

reads pyproject.toml, requirements.txt, and package.json. classifies version
bumps, generates upgrade commands, and formats human-readable reports.

pure python, no network calls by default. set latest_version on deps to
simulate or integrate with real registries.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        tomllib = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------

@dataclass
class Dependency:
    """a single dependency with version info."""

    name: str
    current_version: str
    latest_version: str | None = None
    pinned: bool = False
    dev: bool = False
    source: str = ""


@dataclass
class UpdateInfo:
    """describes an available update for a dependency."""

    dependency: Dependency
    update_type: str  # "major", "minor", "patch", "none"
    breaking: bool = False
    changelog_url: str | None = None


# ---------------------------------------------------------------------------
# version helpers
# ---------------------------------------------------------------------------

_PREFIX_RE = re.compile(r"^[~^>=<!]+")
_VERSION_RE = re.compile(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?")


def parse_version(version_str: str) -> tuple[int, int, int]:
    """strip prefixes and parse semver into (major, minor, patch)."""
    cleaned = _PREFIX_RE.sub("", version_str).strip()
    m = _VERSION_RE.match(cleaned)
    if not m:
        return (0, 0, 0)
    return (
        int(m.group(1)),
        int(m.group(2) or 0),
        int(m.group(3) or 0),
    )


def classify_update(current: str, latest: str) -> str:
    """compare two version strings, return 'major', 'minor', 'patch', or 'none'."""
    cur = parse_version(current)
    lat = parse_version(latest)
    if lat <= cur:
        return "none"
    if lat[0] != cur[0]:
        return "major"
    if lat[1] != cur[1]:
        return "minor"
    if lat[2] != cur[2]:
        return "patch"
    return "none"


# ---------------------------------------------------------------------------
# parsers
# ---------------------------------------------------------------------------

_REQ_LINE_RE = re.compile(
    r"^([A-Za-z0-9_][A-Za-z0-9_.+-]*)"  # package name
    r"\s*"
    r"((?:[><=!~]+)\s*[\d][^\s,;#]*)?",  # optional version spec
)


def parse_requirements(path: str) -> list[Dependency]:
    """parse requirements.txt, handling ==, >=, ~=, comments, blank lines, -r includes."""
    deps: list[Dependency] = []
    base = os.path.dirname(path)

    with open(path) as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("-r ") or line.startswith("-r\t"):
                inc = line.split(None, 1)[1]
                inc_path = inc if os.path.isabs(inc) else os.path.join(base, inc)
                deps.extend(parse_requirements(inc_path))
                continue
            # strip inline comments
            line = line.split("#")[0].strip()
            if not line:
                continue
            m = _REQ_LINE_RE.match(line)
            if not m:
                continue
            name = m.group(1)
            ver_spec = (m.group(2) or "").strip()
            version = ""
            pinned = False
            if ver_spec:
                version = re.sub(r"^[><=!~]+\s*", "", ver_spec)
                pinned = ver_spec.startswith("==")
            deps.append(Dependency(
                name=name,
                current_version=version,
                pinned=pinned,
                source="requirements.txt",
            ))
    return deps


def _parse_dep_string(spec: str, source: str, dev: bool = False) -> Dependency:
    """parse a PEP 508 dependency string like 'requests>=2.28.0'."""
    # strip extras like [python]
    spec = re.sub(r"\[.*?\]", "", spec).strip()
    m = _REQ_LINE_RE.match(spec)
    if not m:
        return Dependency(name=spec.strip(), current_version="", source=source, dev=dev)
    name = m.group(1)
    ver_spec = (m.group(2) or "").strip()
    version = ""
    pinned = False
    if ver_spec:
        version = re.sub(r"^[><=!~]+\s*", "", ver_spec)
        pinned = ver_spec.startswith("==")
    return Dependency(name=name, current_version=version, pinned=pinned, source=source, dev=dev)


def parse_pyproject(path: str) -> list[Dependency]:
    """parse pyproject.toml [project.dependencies] and [project.optional-dependencies]."""
    with open(path, "rb") as f:
        if tomllib is not None:
            data = tomllib.load(f)
        else:
            # minimal fallback: read as text and extract dependency lists
            f.seek(0)
            return _parse_pyproject_fallback(f.read().decode())

    deps: list[Dependency] = []
    project = data.get("project", {})
    for spec in project.get("dependencies", []):
        deps.append(_parse_dep_string(spec, "pyproject.toml"))
    for group, specs in project.get("optional-dependencies", {}).items():
        for spec in specs:
            deps.append(_parse_dep_string(spec, "pyproject.toml", dev=True))
    # dependency-groups (PEP 735)
    for group, specs in data.get("dependency-groups", {}).items():
        for spec in specs:
            if isinstance(spec, str):
                deps.append(_parse_dep_string(spec, "pyproject.toml", dev=True))
    return deps


def _parse_pyproject_fallback(text: str) -> list[Dependency]:
    """rough fallback when tomllib is not available."""
    deps: list[Dependency] = []
    in_deps = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and "dependencies" in stripped.lower():
            in_deps = True
            continue
        if stripped.startswith("[") and in_deps:
            in_deps = False
            continue
        if in_deps and stripped.startswith('"'):
            spec = stripped.strip('",')
            deps.append(_parse_dep_string(spec, "pyproject.toml"))
    return deps


def parse_package_json(path: str) -> list[Dependency]:
    """parse package.json dependencies and devDependencies."""
    with open(path) as f:
        data = json.load(f)
    deps: list[Dependency] = []
    for name, ver in data.get("dependencies", {}).items():
        version = re.sub(r"^[~^>=<]+", "", ver).strip()
        pinned = not any(ver.startswith(c) for c in ("^", "~", ">", "<"))
        deps.append(Dependency(name=name, current_version=version, pinned=pinned, source="package.json"))
    for name, ver in data.get("devDependencies", {}).items():
        version = re.sub(r"^[~^>=<]+", "", ver).strip()
        pinned = not any(ver.startswith(c) for c in ("^", "~", ">", "<"))
        deps.append(Dependency(name=name, current_version=version, pinned=pinned, source="package.json", dev=True))
    return deps


# ---------------------------------------------------------------------------
# discovery
# ---------------------------------------------------------------------------

_MANIFEST_NAMES = ("pyproject.toml", "requirements.txt", "package.json")


def find_manifest(root: str = ".") -> list[str]:
    """find all dependency manifest files in a project directory."""
    found = []
    for name in _MANIFEST_NAMES:
        p = os.path.join(root, name)
        if os.path.isfile(p):
            found.append(p)
    return found


def parse_manifest(path: str) -> list[Dependency]:
    """auto-detect manifest format and parse."""
    name = os.path.basename(path)
    if name == "pyproject.toml":
        return parse_pyproject(path)
    if name == "requirements.txt":
        return parse_requirements(path)
    if name == "package.json":
        return parse_package_json(path)
    return []


# ---------------------------------------------------------------------------
# update logic
# ---------------------------------------------------------------------------

def check_outdated(deps: list[Dependency]) -> list[UpdateInfo]:
    """compare current vs latest versions. expects latest_version pre-set on deps."""
    updates = []
    for dep in deps:
        if not dep.latest_version or not dep.current_version:
            continue
        utype = classify_update(dep.current_version, dep.latest_version)
        if utype == "none":
            continue
        updates.append(UpdateInfo(
            dependency=dep,
            update_type=utype,
            breaking=utype == "major",
        ))
    return updates


def generate_update_commands(updates: list[UpdateInfo]) -> list[str]:
    """generate pip install or npm install commands for updates."""
    cmds = []
    for u in updates:
        dep = u.dependency
        ver = dep.latest_version or dep.current_version
        if dep.source == "package.json":
            flag = " --save-dev" if dep.dev else ""
            cmds.append(f"npm install {dep.name}@{ver}{flag}")
        else:
            cmds.append(f"pip install {dep.name}=={ver}")
    return cmds


def format_update_report(updates: list[UpdateInfo]) -> str:
    """human-readable table of available updates."""
    if not updates:
        return "all dependencies up to date."
    lines = ["dependency updates available:", ""]
    for u in updates:
        dep = u.dependency
        breaking = " [BREAKING]" if u.breaking else ""
        lines.append(
            f"  {dep.name}: {dep.current_version} -> {dep.latest_version} "
            f"({u.update_type}){breaking}"
        )
    lines.append("")
    lines.append(f"{len(updates)} update(s) available.")
    return "\n".join(lines)


def pin_versions(deps: list[Dependency]) -> list[str]:
    """generate pinned requirement lines (name==version)."""
    lines = []
    for dep in deps:
        if dep.current_version:
            lines.append(f"{dep.name}=={dep.current_version}")
        else:
            lines.append(dep.name)
    return lines
