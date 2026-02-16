"""refactor.py - AST-aware refactoring operations.

rename symbols across a project, extract functions, move between modules.
uses symbols.py for finding definitions and references.

in the world: the carpenter's tools. you don't just write code, you reshape it.
"""

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from keanu.analysis.symbols import find_definition, find_references, list_symbols, Symbol, Reference


@dataclass
class RefactorEdit:
    """a single edit produced by a refactoring operation."""
    file: str
    line: int
    old: str
    new: str


@dataclass
class RefactorResult:
    """the result of a refactoring operation."""
    success: bool
    edits: list[RefactorEdit] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False

    @property
    def summary(self) -> str:
        if not self.success:
            return f"failed: {'; '.join(self.errors)}"
        action = "would change" if self.dry_run else "changed"
        return f"{action} {len(self.edits)} locations in {len(self.files_changed)} files"


def rename(old_name: str, new_name: str, root: str = ".",
           dry_run: bool = False) -> RefactorResult:
    """rename a symbol across the entire project.

    finds all definitions and references, replaces them.
    uses word-boundary matching to avoid partial replacements.
    """
    if not old_name or not new_name:
        return RefactorResult(success=False, errors=["both old_name and new_name required"])

    if old_name == new_name:
        return RefactorResult(success=False, errors=["old_name and new_name are the same"])

    root_path = Path(root).resolve()

    # find all occurrences
    defs = find_definition(old_name, root)
    refs = find_references(old_name, root)

    if not defs and not refs:
        return RefactorResult(success=False, errors=[f"'{old_name}' not found in project"])

    # build edit list from references (which includes definition lines too)
    pattern = re.compile(rf'(?<![.\w]){re.escape(old_name)}(?![.\w])')
    edits = []
    files_changed = set()

    # collect all files that need changes
    all_files = set()
    for d in defs:
        all_files.add(d.file)
    for r in refs:
        all_files.add(r.file)

    for rel_file in sorted(all_files):
        filepath = root_path / rel_file
        if not filepath.exists():
            continue

        try:
            lines = filepath.read_text().split("\n")
        except (OSError, UnicodeDecodeError):
            continue

        file_edits = []
        new_lines = []
        for i, line in enumerate(lines):
            new_line = pattern.sub(new_name, line)
            if new_line != line:
                file_edits.append(RefactorEdit(
                    file=rel_file, line=i + 1,
                    old=line.strip(), new=new_line.strip(),
                ))
            new_lines.append(new_line)

        if file_edits:
            edits.extend(file_edits)
            files_changed.add(rel_file)

            if not dry_run:
                filepath.write_text("\n".join(new_lines))

    return RefactorResult(
        success=True,
        edits=edits,
        files_changed=sorted(files_changed),
        dry_run=dry_run,
    )


def extract_function(filepath: str, start_line: int, end_line: int,
                     new_name: str, dry_run: bool = False) -> RefactorResult:
    """extract lines from a function into a new function.

    takes a range of lines, pulls them into a new function, replaces
    the original with a call. detects which variables need to be parameters
    and which are returned.
    """
    path = Path(filepath)
    if not path.exists():
        return RefactorResult(success=False, errors=[f"file not found: {filepath}"])

    try:
        text = path.read_text()
        lines = text.split("\n")
    except (OSError, UnicodeDecodeError) as e:
        return RefactorResult(success=False, errors=[str(e)])

    if start_line < 1 or end_line > len(lines) or start_line > end_line:
        return RefactorResult(success=False, errors=[f"invalid line range: {start_line}-{end_line}"])

    # extract the lines (1-indexed)
    extracted = lines[start_line - 1:end_line]

    # detect indentation of the extracted block
    first_indent = len(extracted[0]) - len(extracted[0].lstrip())
    base_indent = " " * first_indent

    # find variables used in the extracted block
    used_vars = _find_used_names(extracted)
    defined_before = _find_defined_names(lines[:start_line - 1])
    defined_in = _find_defined_names(extracted)
    used_after = _find_used_names(lines[end_line:])

    # parameters: used in extract but defined before
    params = sorted(used_vars & defined_before)

    # returns: defined in extract and used after
    returns = sorted(defined_in & used_after)

    # build the new function
    dedented = [line[first_indent:] if len(line) >= first_indent else line for line in extracted]
    param_str = ", ".join(params)
    func_lines = [f"def {new_name}({param_str}):"]
    for line in dedented:
        func_lines.append(f"    {line}" if line.strip() else "")

    if returns:
        func_lines.append(f"    return {', '.join(returns)}")

    # build the call
    call_args = ", ".join(params)
    if returns:
        ret_vars = ", ".join(returns)
        call_line = f"{base_indent}{ret_vars} = {new_name}({call_args})"
    else:
        call_line = f"{base_indent}{new_name}({call_args})"

    # rebuild the file
    new_lines = lines[:start_line - 1]
    new_lines.append(call_line)
    new_lines.extend(lines[end_line:])

    # insert the new function before the containing function
    containing = _find_containing_function(lines, start_line)
    insert_at = (containing - 1) if containing else (start_line - 1)

    for i, fl in enumerate(func_lines):
        new_lines.insert(insert_at + i, fl)
    new_lines.insert(insert_at + len(func_lines), "")

    edits = [
        RefactorEdit(
            file=filepath, line=start_line,
            old=f"lines {start_line}-{end_line}",
            new=f"extracted to {new_name}({param_str})",
        )
    ]

    if not dry_run:
        path.write_text("\n".join(new_lines))

    return RefactorResult(
        success=True,
        edits=edits,
        files_changed=[filepath],
        dry_run=dry_run,
    )


def move_symbol(name: str, from_file: str, to_file: str,
                root: str = ".", dry_run: bool = False) -> RefactorResult:
    """move a function or class from one module to another.

    moves the definition, adds an import in the old module for backwards
    compat, updates imports across the project.
    """
    root_path = Path(root).resolve()
    from_path = root_path / from_file
    to_path = root_path / to_file

    if not from_path.exists():
        return RefactorResult(success=False, errors=[f"source file not found: {from_file}"])

    # find the symbol in the source file
    defs = find_definition(name, root)
    source_defs = [d for d in defs if d.file == from_file]
    if not source_defs:
        return RefactorResult(success=False, errors=[f"'{name}' not found in {from_file}"])

    sym = source_defs[0]

    try:
        from_text = from_path.read_text()
        from_lines = from_text.split("\n")
    except (OSError, UnicodeDecodeError) as e:
        return RefactorResult(success=False, errors=[str(e)])

    # extract the full definition (function or class) from the source
    start = sym.line - 1
    end = _find_block_end(from_lines, start)
    block = from_lines[start:end]

    if not block:
        return RefactorResult(success=False, errors=[f"could not extract {name} from {from_file}"])

    edits = []
    files_changed = set()

    # add to target file
    to_text = to_path.read_text() if to_path.exists() else ""
    new_to = to_text.rstrip() + "\n\n\n" + "\n".join(block) + "\n"

    if not dry_run:
        to_path.parent.mkdir(parents=True, exist_ok=True)
        to_path.write_text(new_to)

    edits.append(RefactorEdit(
        file=to_file, line=0,
        old="(end of file)",
        new=f"added {sym.kind} {name}",
    ))
    files_changed.add(to_file)

    # remove from source, add re-export for backwards compat
    new_from_lines = from_lines[:start] + from_lines[end:]

    # convert to_file to module path for import
    to_module = str(to_path.relative_to(root_path)).replace("/", ".").replace(".py", "")
    re_export = f"from {to_module} import {name}  # moved"

    # add re-export at the top (after existing imports)
    import_end = _find_import_end(new_from_lines)
    new_from_lines.insert(import_end, re_export)

    if not dry_run:
        from_path.write_text("\n".join(new_from_lines))

    edits.append(RefactorEdit(
        file=from_file, line=sym.line,
        old=f"{sym.kind} {name} definition",
        new=f"moved to {to_file}, re-export added",
    ))
    files_changed.add(from_file)

    return RefactorResult(
        success=True,
        edits=edits,
        files_changed=sorted(files_changed),
        dry_run=dry_run,
    )


# ============================================================
# HELPERS
# ============================================================

def _find_used_names(lines: list[str]) -> set[str]:
    """find variable names used in a block of code."""
    names = set()
    for line in lines:
        # simple heuristic: word characters that look like identifiers
        tokens = re.findall(r'\b([a-zA-Z_]\w*)\b', line)
        names.update(tokens)
    # remove Python keywords and builtins
    keywords = {
        'def', 'class', 'return', 'if', 'else', 'elif', 'for', 'while',
        'import', 'from', 'as', 'try', 'except', 'finally', 'with',
        'True', 'False', 'None', 'and', 'or', 'not', 'in', 'is',
        'print', 'len', 'range', 'str', 'int', 'float', 'list', 'dict',
        'set', 'tuple', 'bool', 'type', 'isinstance', 'hasattr', 'getattr',
        'self', 'cls', 'super', 'pass', 'break', 'continue', 'raise',
        'yield', 'lambda', 'global', 'nonlocal', 'assert', 'del',
    }
    return names - keywords


def _find_defined_names(lines: list[str]) -> set[str]:
    """find variable names defined (assigned) in a block of code."""
    names = set()
    for line in lines:
        stripped = line.strip()
        # simple assignment: name = ...
        match = re.match(r'^([a-zA-Z_]\w*)\s*=', stripped)
        if match and not stripped.startswith(('def ', 'class ')):
            names.add(match.group(1))
        # for loop variable
        match = re.match(r'^for\s+(\w+)', stripped)
        if match:
            names.add(match.group(1))
    return names


def _find_containing_function(lines: list[str], target_line: int) -> Optional[int]:
    """find the line number of the function containing target_line."""
    for i in range(target_line - 2, -1, -1):
        stripped = lines[i].strip()
        if stripped.startswith("def ") or stripped.startswith("async def "):
            return i + 1
    return None


def _find_block_end(lines: list[str], start: int) -> int:
    """find where a def/class block ends based on indentation."""
    if start >= len(lines):
        return start

    first_line = lines[start]
    base_indent = len(first_line) - len(first_line.lstrip())

    for i in range(start + 1, len(lines)):
        line = lines[i]
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= base_indent:
            return i

    return len(lines)


def _find_import_end(lines: list[str]) -> int:
    """find the line after the last import statement."""
    last_import = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            last_import = i + 1
        elif stripped and not stripped.startswith("#") and not stripped.startswith('"""') and last_import > 0:
            break
    return last_import
