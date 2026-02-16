"""security.py - secret detection, dependency scanning, audit logging.

catches secrets before they leak, scans dependencies for known vulns,
logs every ability execution for accountability.

in the world: the guardian. watches the gates so the creator can move fast.
"""

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from keanu.paths import keanu_home


_AUDIT_LOG = keanu_home() / "audit.jsonl"


# ============================================================
# SECRET DETECTION
# ============================================================

@dataclass
class SecretFinding:
    """a detected secret in a file."""
    file: str
    line: int
    category: str   # api_key, password, token, private_key, etc.
    snippet: str    # redacted preview of the match
    confidence: float  # 0.0-1.0

    def __str__(self):
        return f"{self.file}:{self.line} [{self.category}] {self.snippet}"


# patterns: (name, regex, confidence)
_SECRET_PATTERNS: list[tuple[str, re.Pattern, float]] = [
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}"), 0.95),
    ("aws_secret", re.compile(r"(?i)aws.{0,20}secret.{0,20}['\"][0-9a-zA-Z/+]{40}['\"]"), 0.90),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,}"), 0.95),
    ("github_classic", re.compile(r"ghp_[A-Za-z0-9]{36}"), 0.95),
    ("slack_token", re.compile(r"xox[baprs]-[0-9]{10,13}-[0-9a-zA-Z-]+"), 0.90),
    ("stripe_key", re.compile(r"sk_live_[0-9a-zA-Z]{24,}"), 0.95),
    ("stripe_test", re.compile(r"sk_test_[0-9a-zA-Z]{24,}"), 0.80),
    ("anthropic_key", re.compile(r"sk-ant-[a-zA-Z0-9-]{20,}"), 0.95),
    ("openai_key", re.compile(r"sk-[a-zA-Z0-9]{20,}"), 0.85),
    ("generic_api_key", re.compile(r"(?i)(api[_-]?key|apikey)\s*[:=]\s*['\"][a-zA-Z0-9_\-]{16,}['\"]"), 0.75),
    ("generic_secret", re.compile(r"(?i)(secret|password|passwd|pwd)\s*[:=]\s*['\"][^\s'\"]{8,}['\"]"), 0.70),
    ("generic_token", re.compile(r"(?i)(token|bearer)\s*[:=]\s*['\"][a-zA-Z0-9_\-\.]{20,}['\"]"), 0.70),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----"), 0.99),
    ("connection_string", re.compile(r"(?i)(postgres|mysql|mongodb|redis)://[^\s]+:[^\s]+@"), 0.85),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9-_]+\.eyJ[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+"), 0.60),
]

# files to always skip
_SKIP_EXTENSIONS = {".pyc", ".pyo", ".so", ".dylib", ".dll", ".exe", ".bin",
                    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff",
                    ".woff2", ".ttf", ".eot", ".zip", ".gz", ".tar", ".bz2"}

_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv",
              ".tox", ".mypy_cache", ".pytest_cache", "dist", "build",
              ".eggs", "*.egg-info"}


def scan_secrets(path: str, max_files: int = 500) -> list[SecretFinding]:
    """scan a file or directory for secrets."""
    p = Path(path)
    if p.is_file():
        return _scan_file_secrets(p)

    findings = []
    file_count = 0
    for f in _walk_files(p, max_files):
        findings.extend(_scan_file_secrets(f))
        file_count += 1
    return findings


def _scan_file_secrets(filepath: Path) -> list[SecretFinding]:
    """scan a single file for secrets."""
    if filepath.suffix in _SKIP_EXTENSIONS:
        return []
    try:
        text = filepath.read_text(errors="ignore")
    except (OSError, UnicodeDecodeError):
        return []

    findings = []
    for line_num, line in enumerate(text.split("\n"), 1):
        for name, pattern, confidence in _SECRET_PATTERNS:
            match = pattern.search(line)
            if match:
                # redact the actual secret
                snippet = _redact(line.strip(), match)
                findings.append(SecretFinding(
                    file=str(filepath),
                    line=line_num,
                    category=name,
                    snippet=snippet,
                    confidence=confidence,
                ))
    return findings


def _redact(line: str, match: re.Match) -> str:
    """redact a secret match, showing context but not the value."""
    start, end = match.span()
    secret = match.group()
    if len(secret) > 8:
        redacted = secret[:4] + "****" + secret[-4:]
    else:
        redacted = "****"
    return line[:start] + redacted + line[end:]


def check_secrets_in_staged() -> list[SecretFinding]:
    """check staged git files for secrets before commit."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "diff", "--staged", "--name-only"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return []
    except Exception:
        return []

    findings = []
    for filename in result.stdout.strip().split("\n"):
        if filename and Path(filename).exists():
            findings.extend(_scan_file_secrets(Path(filename)))
    return findings


# ============================================================
# SENSITIVE FILE DETECTION
# ============================================================

_SENSITIVE_FILES = {
    ".env", ".env.local", ".env.production", ".env.development",
    "credentials.json", "service-account.json",
    "id_rsa", "id_ed25519", "id_ecdsa",
    ".npmrc", ".pypirc", ".netrc",
    "keystore.jks", "keystore.p12",
}

_SENSITIVE_PATTERNS = [
    re.compile(r"\.env(\.\w+)?$"),
    re.compile(r".*\.pem$"),
    re.compile(r".*\.key$"),
    re.compile(r".*credential.*\.json$", re.IGNORECASE),
    re.compile(r".*secret.*\.ya?ml$", re.IGNORECASE),
]


def is_sensitive_file(filepath: str) -> bool:
    """check if a file is likely sensitive."""
    name = Path(filepath).name
    if name in _SENSITIVE_FILES:
        return True
    return any(p.match(name) for p in _SENSITIVE_PATTERNS)


def check_gitignore_coverage(root: str = ".") -> list[str]:
    """check which sensitive files are NOT in .gitignore."""
    root_path = Path(root)
    gitignore = root_path / ".gitignore"

    ignored_patterns = set()
    if gitignore.exists():
        for line in gitignore.read_text().split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                ignored_patterns.add(line)

    unprotected = []
    for f in _walk_files(root_path, max_files=1000):
        if is_sensitive_file(str(f)):
            rel = str(f.relative_to(root_path))
            # check if any gitignore pattern matches
            if not any(_gitignore_matches(pattern, rel) for pattern in ignored_patterns):
                unprotected.append(rel)
    return unprotected


def _gitignore_matches(pattern: str, filepath: str) -> bool:
    """simple gitignore pattern matching."""
    import fnmatch
    name = Path(filepath).name
    return fnmatch.fnmatch(filepath, pattern) or fnmatch.fnmatch(name, pattern)


# ============================================================
# DEPENDENCY SCANNING
# ============================================================

@dataclass
class DepVuln:
    """a dependency vulnerability."""
    package: str
    installed_version: str
    advisory: str
    severity: str  # low, medium, high, critical
    fix_version: str = ""


def scan_dependencies(root: str = ".") -> list[DepVuln]:
    """scan dependencies for known vulnerabilities."""
    import subprocess
    root_path = Path(root)

    vulns = []

    # try pip-audit for Python
    if (root_path / "requirements.txt").exists() or (root_path / "pyproject.toml").exists():
        vulns.extend(_scan_pip_audit(root))

    # try npm audit for Node
    if (root_path / "package.json").exists():
        vulns.extend(_scan_npm_audit(root))

    return vulns


def _scan_pip_audit(root: str) -> list[DepVuln]:
    """run pip-audit if available."""
    import subprocess
    try:
        result = subprocess.run(
            ["pip-audit", "--format", "json", "--desc"],
            capture_output=True, text=True, timeout=60,
            cwd=root,
        )
        if result.returncode not in (0, 1):
            return []
        data = json.loads(result.stdout)
        vulns = []
        for dep in data.get("dependencies", []):
            for vuln in dep.get("vulns", []):
                vulns.append(DepVuln(
                    package=dep["name"],
                    installed_version=dep["version"],
                    advisory=vuln.get("id", ""),
                    severity=vuln.get("fix_versions", [""])[0] if vuln.get("fix_versions") else "",
                    fix_version=vuln.get("fix_versions", [""])[0] if vuln.get("fix_versions") else "",
                ))
        return vulns
    except (FileNotFoundError, json.JSONDecodeError, subprocess.TimeoutExpired):
        return []


def _scan_npm_audit(root: str) -> list[DepVuln]:
    """run npm audit if available."""
    import subprocess
    try:
        result = subprocess.run(
            ["npm", "audit", "--json"],
            capture_output=True, text=True, timeout=60,
            cwd=root,
        )
        data = json.loads(result.stdout)
        vulns = []
        for name, advisory in data.get("advisories", {}).items():
            vulns.append(DepVuln(
                package=advisory.get("module_name", ""),
                installed_version="",
                advisory=advisory.get("title", ""),
                severity=advisory.get("severity", "unknown"),
                fix_version=advisory.get("patched_versions", ""),
            ))
        return vulns
    except (FileNotFoundError, json.JSONDecodeError, subprocess.TimeoutExpired):
        return []


# ============================================================
# AUDIT LOG
# ============================================================

@dataclass
class AuditEntry:
    """an audit log entry."""
    timestamp: float
    action: str      # ability name or operation
    args: dict        # sanitized args (no secrets)
    result: str       # ok, error, denied
    user: str = ""
    duration_ms: int = 0


def log_audit(action: str, args: dict, result: str, duration_ms: int = 0):
    """log an ability execution to the audit trail."""
    _AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": time.time(),
        "action": action,
        "args": _sanitize_args(args),
        "result": result,
        "duration_ms": duration_ms,
    }
    try:
        with open(_AUDIT_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def get_audit_log(limit: int = 50) -> list[dict]:
    """read recent audit log entries."""
    if not _AUDIT_LOG.exists():
        return []
    entries = []
    try:
        for line in _AUDIT_LOG.read_text().strip().split("\n"):
            if line.strip():
                entries.append(json.loads(line))
    except (json.JSONDecodeError, OSError):
        pass
    return entries[-limit:]


def _sanitize_args(args: dict) -> dict:
    """remove sensitive values from args before logging."""
    sanitized = {}
    sensitive_keys = {"password", "secret", "token", "key", "credential", "auth"}
    for k, v in args.items():
        if any(s in k.lower() for s in sensitive_keys):
            sanitized[k] = "****"
        elif isinstance(v, str) and len(v) > 500:
            sanitized[k] = v[:100] + "...(truncated)"
        else:
            sanitized[k] = v
    return sanitized


# ============================================================
# HELPERS
# ============================================================

def _walk_files(root: Path, max_files: int = 500):
    """walk files, skipping binary and hidden dirs."""
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        # skip hidden/vendor dirs
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            if count >= max_files:
                return
            filepath = Path(dirpath) / name
            if filepath.suffix not in _SKIP_EXTENSIONS:
                yield filepath
                count += 1
