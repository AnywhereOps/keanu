"""errors.py - parse errors into structured data the agent can act on.

raw stderr is noise. structured errors are signal. this module parses
Python tracebacks, JS stack traces, Go panics, and common tool output
into a format the agent loop can reason about.

in the world: translating screams into sentences.
"""

from dataclasses import dataclass, field
import re


@dataclass
class ParsedError:
    """a structured error the agent can reason about."""
    category: str = ""       # syntax, runtime, import, type, assertion, timeout, unknown
    message: str = ""        # the actual error message
    file: str = ""           # file where the error occurred
    line: int = 0            # line number
    function: str = ""       # function name if available
    traceback: list = field(default_factory=list)  # list of frame dicts
    suggestion: str = ""     # what to try next
    raw: str = ""            # original error text

    @property
    def location(self) -> str:
        """file:line shorthand."""
        if self.file and self.line:
            return f"{self.file}:{self.line}"
        if self.file:
            return self.file
        return ""

    def summary(self) -> str:
        """one-line summary for the agent."""
        loc = f" at {self.location}" if self.location else ""
        sug = f" Try: {self.suggestion}" if self.suggestion else ""
        return f"[{self.category}]{loc} {self.message}{sug}"


def parse(text: str) -> ParsedError:
    """parse error text into a structured ParsedError.

    tries each parser in order. first match wins.
    """
    text = text.strip()
    if not text:
        return ParsedError(category="unknown", message="(empty error)", raw=text)

    for parser in [
        _parse_python_traceback,
        _parse_pytest_failure,
        _parse_js_error,
        _parse_go_panic,
        _parse_generic,
    ]:
        result = parser(text)
        if result is not None:
            result.raw = text[:2000]
            if not result.suggestion:
                result.suggestion = _suggest(result)
            return result

    return ParsedError(
        category="unknown",
        message=text[:200],
        raw=text[:2000],
        suggestion=_suggest_from_text(text),
    )


# ============================================================
# PYTHON
# ============================================================

_PY_TB_FRAME = re.compile(
    r'File "([^"]+)", line (\d+)(?:, in (.+))?'
)

_PY_ERROR_LINE = re.compile(
    r'^(\w+(?:\.\w+)*(?:Error|Exception|Warning)): (.+)',
    re.MULTILINE,
)


def _parse_python_traceback(text: str) -> ParsedError | None:
    """parse a Python traceback."""
    if "Traceback (most recent call last):" not in text:
        return None

    frames = []
    for match in _PY_TB_FRAME.finditer(text):
        frames.append({
            "file": match.group(1),
            "line": int(match.group(2)),
            "function": match.group(3) or "",
        })

    error_match = _PY_ERROR_LINE.search(text)
    if not error_match:
        # sometimes the error line is the last non-empty line
        lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
        error_line = lines[-1] if lines else text[:200]
        category = _categorize_python(error_line)
        message = error_line
    else:
        error_type = error_match.group(1)
        message = error_match.group(2)
        category = _categorize_python(error_type)

    last_frame = frames[-1] if frames else {}

    return ParsedError(
        category=category,
        message=message[:300],
        file=last_frame.get("file", ""),
        line=last_frame.get("line", 0),
        function=last_frame.get("function", ""),
        traceback=frames,
    )


def _categorize_python(error_text: str) -> str:
    """categorize a Python error by type."""
    et = error_text.lower()
    if "syntaxerror" in et or "indentationerror" in et:
        return "syntax"
    if "importerror" in et or "modulenotfounderror" in et:
        return "import"
    if "typeerror" in et:
        return "type"
    if "nameerror" in et:
        return "name"
    if "attributeerror" in et:
        return "attribute"
    if "valueerror" in et:
        return "value"
    if "keyerror" in et:
        return "key"
    if "indexerror" in et:
        return "index"
    if "filenotfounderror" in et or "oserror" in et or "ioerror" in et:
        return "io"
    if "assertionerror" in et:
        return "assertion"
    if "timeout" in et:
        return "timeout"
    if "permissionerror" in et:
        return "permission"
    if "connectionerror" in et or "connectionrefused" in et:
        return "connection"
    return "runtime"


# ============================================================
# PYTEST
# ============================================================

_PYTEST_FAIL = re.compile(
    r'FAILED ([\w/\\.]+)::(\w+)(?:::(\w+))?\s*[-=]',
)

_PYTEST_SHORT = re.compile(
    r'E\s+(\w+(?:Error|Exception)): (.+)',
)

_PYTEST_ASSERT = re.compile(
    r'E\s+assert (.+)',
)


def _parse_pytest_failure(text: str) -> ParsedError | None:
    """parse pytest failure output."""
    if "FAILED" not in text and "ERRORS" not in text:
        return None
    if "pytest" not in text.lower() and "test" not in text.lower():
        return None

    # try to find the specific failure
    fail_match = _PYTEST_FAIL.search(text)
    short_match = _PYTEST_SHORT.search(text)
    assert_match = _PYTEST_ASSERT.search(text)

    file_path = ""
    function = ""
    if fail_match:
        file_path = fail_match.group(1)
        function = fail_match.group(3) or fail_match.group(2)

    if short_match:
        message = f"{short_match.group(1)}: {short_match.group(2)}"
        category = _categorize_python(short_match.group(1))
    elif assert_match:
        message = f"assertion failed: {assert_match.group(1)}"
        category = "assertion"
    else:
        # grab the last E line
        e_lines = [l for l in text.split("\n") if l.strip().startswith("E ")]
        message = e_lines[-1].strip()[2:] if e_lines else "test failed"
        category = "test_failure"

    # find line number from traceback in pytest output
    line = 0
    line_match = re.search(r':(\d+):', text)
    if line_match:
        line = int(line_match.group(1))

    return ParsedError(
        category=category,
        message=message[:300],
        file=file_path,
        line=line,
        function=function,
    )


# ============================================================
# JAVASCRIPT / NODE
# ============================================================

_JS_ERROR = re.compile(
    r'(\w+Error): (.+?)(?:\n|$)',
)

_JS_FRAME = re.compile(
    r'at (?:(.+?) \()?(.+?):(\d+):\d+\)?',
)


def _parse_js_error(text: str) -> ParsedError | None:
    """parse a JS/Node error with stack trace."""
    error_match = _JS_ERROR.search(text)
    if not error_match:
        return None
    if "    at " not in text:
        return None

    error_type = error_match.group(1)
    message = error_match.group(2)

    frames = []
    for match in _JS_FRAME.finditer(text):
        frames.append({
            "function": match.group(1) or "",
            "file": match.group(2),
            "line": int(match.group(3)),
        })

    first_frame = frames[0] if frames else {}

    category = "runtime"
    et = error_type.lower()
    if "syntax" in et:
        category = "syntax"
    elif "type" in et:
        category = "type"
    elif "reference" in et:
        category = "name"
    elif "range" in et:
        category = "index"

    return ParsedError(
        category=category,
        message=message[:300],
        file=first_frame.get("file", ""),
        line=first_frame.get("line", 0),
        function=first_frame.get("function", ""),
        traceback=frames,
    )


# ============================================================
# GO
# ============================================================

_GO_PANIC = re.compile(r'panic: (.+)')
_GO_FRAME = re.compile(r'(\S+\.go):(\d+)')


def _parse_go_panic(text: str) -> ParsedError | None:
    """parse a Go panic."""
    panic_match = _GO_PANIC.search(text)
    if not panic_match:
        return None

    message = panic_match.group(1)

    frames = []
    for match in _GO_FRAME.finditer(text):
        frames.append({
            "file": match.group(1),
            "line": int(match.group(2)),
        })

    first_frame = frames[0] if frames else {}

    return ParsedError(
        category="panic",
        message=message[:300],
        file=first_frame.get("file", ""),
        line=first_frame.get("line", 0),
        traceback=frames,
    )


# ============================================================
# GENERIC
# ============================================================

def _parse_generic(text: str) -> ParsedError | None:
    """try to extract something useful from any error text."""
    # look for file:line patterns
    loc_match = re.search(r'([\w/\\.]+\.\w+):(\d+)', text)
    file_path = loc_match.group(1) if loc_match else ""
    line = int(loc_match.group(2)) if loc_match else 0

    # look for common error keywords
    lines = text.strip().split("\n")
    error_line = ""
    for l in reversed(lines):
        l = l.strip()
        if any(kw in l.lower() for kw in ["error", "failed", "exception", "fatal"]):
            error_line = l
            break
    if not error_line:
        error_line = lines[-1] if lines else text[:200]

    category = _categorize_generic(text)
    if category == "unknown":
        return None

    return ParsedError(
        category=category,
        message=error_line[:300],
        file=file_path,
        line=line,
    )


def _categorize_generic(text: str) -> str:
    """categorize error text by keywords."""
    t = text.lower()
    if "command not found" in t:
        return "missing_tool"
    if "permission denied" in t or "access denied" in t:
        return "permission"
    if "timeout" in t or "timed out" in t:
        return "timeout"
    if "connection refused" in t or "econnrefused" in t:
        return "connection"
    if "not found" in t or "no such file" in t:
        return "io"
    if "out of memory" in t or "oom" in t:
        return "memory"
    if "disk full" in t or "no space" in t:
        return "disk"
    if "syntax error" in t:
        return "syntax"
    return "unknown"


# ============================================================
# SUGGESTIONS
# ============================================================

_SUGGESTIONS = {
    "syntax": "check the file for syntax errors. read it first, look at the line number.",
    "import": "check if the module is installed. look at requirements.txt or pyproject.toml.",
    "type": "check the types being passed. read the function signature.",
    "name": "variable or function not defined. check spelling and scope.",
    "attribute": "object doesn't have that attribute. check the class definition.",
    "value": "wrong value passed. check the expected input format.",
    "key": "dictionary key doesn't exist. check the keys with a read or print.",
    "index": "list index out of range. check the length.",
    "io": "file not found. check the path exists. use ls to verify.",
    "assertion": "test assertion failed. read the test, understand what it expects.",
    "timeout": "operation timed out. check if the service is running.",
    "permission": "permission denied. check file permissions.",
    "connection": "can't connect. check if the service is running and the URL is right.",
    "memory": "out of memory. check for large allocations or infinite loops.",
    "missing_tool": "command not found. check if the tool is installed.",
    "panic": "Go panic. check the panic message and goroutine stack.",
    "test_failure": "test failed. read the test file and the assertion that failed.",
    "runtime": "runtime error. read the traceback from bottom to top.",
}


def _suggest(error: ParsedError) -> str:
    """suggest a next step based on error category."""
    return _SUGGESTIONS.get(error.category, "")


def _suggest_from_text(text: str) -> str:
    """suggest from raw text when no parser matched."""
    t = text.lower()
    if "pip install" in t:
        return "install the missing package."
    if "npm install" in t or "yarn add" in t:
        return "install the missing package."
    if "docker" in t:
        return "check if docker is running."
    return ""
