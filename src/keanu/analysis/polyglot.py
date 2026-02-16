"""polyglot.py - multi-language code analysis.

regex-based analysis for JS/TS/Go/Rust. provides the same interface
as symbols.py (find_definition, find_references, list_symbols) but
for languages beyond Python.

in the world: the rosetta stone. same questions, different languages.
you ask "where is this defined?" and it answers regardless of tongue.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Symbol:
    """a code symbol found in a file."""
    name: str
    kind: str           # function, class, method, variable, type, interface
    file: str
    line: int
    language: str
    signature: str = ""
    exported: bool = False


@dataclass
class Reference:
    """a reference to a symbol."""
    name: str
    file: str
    line: int
    context: str = ""


# ============================================================
# LANGUAGE DETECTION
# ============================================================

LANG_MAP = {
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".java": "java",
    ".kt": "kotlin",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
}


def detect_language(path: str) -> str:
    """detect language from file extension."""
    ext = Path(path).suffix.lower()
    return LANG_MAP.get(ext, "")


# ============================================================
# PATTERNS PER LANGUAGE
# ============================================================

# each entry: (regex, kind)
_JS_PATTERNS = [
    (r'(?:export\s+)?(?:async\s+)?function\s+(\w+)', "function"),
    (r'(?:export\s+)?class\s+(\w+)', "class"),
    (r'(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\(', "function"),
    (r'(?:export\s+)?const\s+(\w+)\s*=\s*\{', "variable"),
    (r'(?:export\s+)?(?:let|const|var)\s+(\w+)\s*=', "variable"),
    (r'(\w+)\s*\([^)]*\)\s*\{', "method"),
]

_TS_PATTERNS = _JS_PATTERNS + [
    (r'(?:export\s+)?interface\s+(\w+)', "interface"),
    (r'(?:export\s+)?type\s+(\w+)\s*=', "type"),
    (r'(?:export\s+)?enum\s+(\w+)', "enum"),
]

_GO_PATTERNS = [
    (r'func\s+(\w+)\s*\(', "function"),
    (r'func\s+\(\w+\s+\*?\w+\)\s+(\w+)\s*\(', "method"),
    (r'type\s+(\w+)\s+struct\b', "struct"),
    (r'type\s+(\w+)\s+interface\b', "interface"),
    (r'type\s+(\w+)\s+', "type"),
    (r'var\s+(\w+)\s+', "variable"),
    (r'const\s+(\w+)\s*=', "variable"),
]

_RUST_PATTERNS = [
    (r'(?:pub\s+)?fn\s+(\w+)', "function"),
    (r'(?:pub\s+)?struct\s+(\w+)', "struct"),
    (r'(?:pub\s+)?enum\s+(\w+)', "enum"),
    (r'(?:pub\s+)?trait\s+(\w+)', "trait"),
    (r'(?:pub\s+)?type\s+(\w+)', "type"),
    (r'impl(?:<[^>]*>)?\s+(\w+)', "impl"),
    (r'(?:pub\s+)?(?:static|const)\s+(\w+)', "variable"),
    (r'(?:pub\s+)?mod\s+(\w+)', "module"),
]

_RUBY_PATTERNS = [
    (r'def\s+(\w+)', "function"),
    (r'class\s+(\w+)', "class"),
    (r'module\s+(\w+)', "module"),
    (r'attr_(?:reader|writer|accessor)\s+:(\w+)', "variable"),
]

_JAVA_PATTERNS = [
    (r'(?:public|private|protected)?\s*(?:static\s+)?(?:final\s+)?\w+\s+(\w+)\s*\(', "method"),
    (r'(?:public\s+)?class\s+(\w+)', "class"),
    (r'(?:public\s+)?interface\s+(\w+)', "interface"),
    (r'(?:public\s+)?enum\s+(\w+)', "enum"),
]

_C_PATTERNS = [
    (r'(?:static\s+)?(?:\w+\s+)+(\w+)\s*\([^)]*\)\s*\{', "function"),
    (r'typedef\s+struct\s+\w*\s*\{[^}]*\}\s*(\w+)', "struct"),
    (r'struct\s+(\w+)\s*\{', "struct"),
    (r'enum\s+(\w+)\s*\{', "enum"),
    (r'#define\s+(\w+)', "macro"),
]

LANGUAGE_PATTERNS = {
    "javascript": _JS_PATTERNS,
    "typescript": _TS_PATTERNS,
    "go": _GO_PATTERNS,
    "rust": _RUST_PATTERNS,
    "ruby": _RUBY_PATTERNS,
    "java": _JAVA_PATTERNS,
    "kotlin": _JAVA_PATTERNS,
    "c": _C_PATTERNS,
    "cpp": _C_PATTERNS,
}


def _is_exported(line: str, language: str) -> bool:
    """check if a symbol definition is exported."""
    if language in ("javascript", "typescript"):
        return "export" in line
    elif language == "go":
        # Go exports start with uppercase
        return False  # checked separately
    elif language == "rust":
        return "pub " in line
    elif language in ("java", "kotlin"):
        return "public" in line
    return False


# ============================================================
# SYMBOL FINDING
# ============================================================

def list_symbols(path: str) -> list[Symbol]:
    """list all symbols defined in a file."""
    language = detect_language(path)
    if not language:
        return []

    patterns = LANGUAGE_PATTERNS.get(language, [])
    if not patterns:
        return []

    try:
        content = Path(path).read_text(errors="replace")
    except OSError:
        return []

    symbols = []
    for i, line in enumerate(content.split("\n"), 1):
        for regex, kind in patterns:
            match = re.search(regex, line)
            if match:
                name = match.group(1)
                exported = _is_exported(line, language)

                # Go: uppercase first letter means exported
                if language == "go" and name[0].isupper():
                    exported = True

                symbols.append(Symbol(
                    name=name,
                    kind=kind,
                    file=path,
                    line=i,
                    language=language,
                    signature=line.strip(),
                    exported=exported,
                ))
                break  # one symbol per line

    return symbols


def find_definition(name: str, root: str = ".") -> list[Symbol]:
    """find where a symbol is defined across the project."""
    results = []
    root_path = Path(root)

    for ext in LANG_MAP:
        for path in root_path.rglob(f"*{ext}"):
            # skip vendor/node_modules
            parts = set(path.parts)
            if parts & {"node_modules", "vendor", ".git", "__pycache__", "dist", "build"}:
                continue

            syms = list_symbols(str(path))
            for s in syms:
                if s.name == name:
                    results.append(s)

    return results


def find_references(name: str, root: str = ".", extensions: list[str] = None) -> list[Reference]:
    """find all references to a symbol name across the project."""
    results = []
    root_path = Path(root)
    exts = extensions or list(LANG_MAP.keys())

    for ext in exts:
        for path in root_path.rglob(f"*{ext}"):
            parts = set(path.parts)
            if parts & {"node_modules", "vendor", ".git", "__pycache__", "dist", "build"}:
                continue

            try:
                content = Path(path).read_text(errors="replace")
            except OSError:
                continue

            for i, line in enumerate(content.split("\n"), 1):
                if name in line:
                    results.append(Reference(
                        name=name,
                        file=str(path),
                        line=i,
                        context=line.strip()[:100],
                    ))

    return results


def find_imports(path: str) -> list[str]:
    """find all imports in a file."""
    language = detect_language(path)

    try:
        content = Path(path).read_text(errors="replace")
    except OSError:
        return []

    imports = []

    if language in ("javascript", "typescript"):
        # import ... from 'module' or require('module')
        for match in re.finditer(r"""(?:import|require)\s*\(?['"]([^'"]+)['"]""", content):
            imports.append(match.group(1))
        # import ... from "module"
        for match in re.finditer(r"""from\s+['"]([^'"]+)['"]""", content):
            if match.group(1) not in imports:
                imports.append(match.group(1))
    elif language == "go":
        for match in re.finditer(r'"([^"]+)"', content):
            # only in import blocks
            imports.append(match.group(1))
    elif language == "rust":
        for match in re.finditer(r'use\s+([\w:]+)', content):
            imports.append(match.group(1))
    elif language == "ruby":
        for match in re.finditer(r"require\s+['\"]([^'\"]+)['\"]", content):
            imports.append(match.group(1))
    elif language in ("java", "kotlin"):
        for match in re.finditer(r'import\s+([\w.]+)', content):
            imports.append(match.group(1))
    elif language in ("c", "cpp"):
        for match in re.finditer(r'#include\s+[<"]([^>"]+)[>"]', content):
            imports.append(match.group(1))

    return imports


def project_languages(root: str = ".") -> dict[str, int]:
    """count files per language in a project."""
    root_path = Path(root)
    counts: dict[str, int] = {}

    for ext, lang in LANG_MAP.items():
        for _ in root_path.rglob(f"*{ext}"):
            counts[lang] = counts.get(lang, 0) + 1

    return dict(sorted(counts.items(), key=lambda x: -x[1]))
