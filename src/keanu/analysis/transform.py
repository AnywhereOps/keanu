"""transform.py - AST-based Python code transformations.

safe, structure-aware code modifications. parse the tree, reshape it,
give it back. used by refactor.py and codegen.py when you need more
than regex but less than a rewrite.

in the world: the chisel. refactor.py is the carpenter, this is the blade.
"""

import ast
import re
from typing import Optional


# ============================================================
# IMPORTS
# ============================================================

def add_import(source: str, module: str, names: list[str] = None) -> str:
    """add an import statement. deduplicates, places after existing imports."""
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)

    # check if already imported
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and not names:
            for alias in node.names:
                if alias.name == module:
                    return source
        if isinstance(node, ast.ImportFrom) and names:
            if node.module == module:
                existing = {a.name for a in node.names}
                needed = set(names) - existing
                if not needed:
                    return source
                # add missing names to existing from-import
                all_names = sorted(existing | set(names))
                name_str = ", ".join(all_names)
                new_line = f"from {module} import {name_str}\n"
                start = node.lineno - 1
                end = node.end_lineno
                return "".join(lines[:start]) + new_line + "".join(lines[end:])

    # build the new import line
    if names:
        name_str = ", ".join(names)
        new_line = f"from {module} import {name_str}\n"
    else:
        new_line = f"import {module}\n"

    # find insertion point: after last import
    insert_at = _last_import_line(tree)
    if insert_at == 0:
        # no imports, place after docstring/comments
        insert_at = _after_docstring(lines)

    return "".join(lines[:insert_at]) + new_line + "".join(lines[insert_at:])


def remove_import(source: str, module: str, name: str = "") -> str:
    """remove an import. if name given, remove just that name from a from-import."""
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and not name:
            for alias in node.names:
                if alias.name == module:
                    start = node.lineno - 1
                    end = node.end_lineno
                    return "".join(lines[:start]) + "".join(lines[end:])

        if isinstance(node, ast.ImportFrom) and node.module == module:
            if not name:
                # remove entire from-import
                start = node.lineno - 1
                end = node.end_lineno
                return "".join(lines[:start]) + "".join(lines[end:])
            # remove specific name
            existing = [a.name for a in node.names]
            if name not in existing:
                return source
            remaining = [n for n in existing if n != name]
            if not remaining:
                start = node.lineno - 1
                end = node.end_lineno
                return "".join(lines[:start]) + "".join(lines[end:])
            name_str = ", ".join(remaining)
            new_line = f"from {module} import {name_str}\n"
            start = node.lineno - 1
            end = node.end_lineno
            return "".join(lines[:start]) + new_line + "".join(lines[end:])

    return source


def unused_imports(source: str) -> list[str]:
    """find imports never referenced in the code body."""
    tree = ast.parse(source)

    # collect all imported names
    imported = {}  # name -> display string
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name
                imported[local] = alias.name
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                local = alias.asname or alias.name
                imported[local] = f"{node.module}.{alias.name}"

    # collect all Name references outside import statements
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            # handle module.attr references
            root = _attr_root(node)
            if root:
                used.add(root)

    unused = []
    for local_name, display in sorted(imported.items()):
        if local_name not in used:
            unused.append(display)

    return unused


# ============================================================
# RENAME
# ============================================================

def rename_function(source: str, old_name: str, new_name: str) -> str:
    """rename a function definition and all calls to it."""
    tree = ast.parse(source)

    class FuncRenamer(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            self.generic_visit(node)
            if node.name == old_name:
                node.name = new_name
            return node

        def visit_AsyncFunctionDef(self, node):
            self.generic_visit(node)
            if node.name == old_name:
                node.name = new_name
            return node

        def visit_Call(self, node):
            self.generic_visit(node)
            if isinstance(node.func, ast.Name) and node.func.id == old_name:
                node.func.id = new_name
            return node

        def visit_Name(self, node):
            # catch references like passing function as argument
            if node.id == old_name:
                node.id = new_name
            return node

    tree = FuncRenamer().visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + "\n"


def rename_variable(source: str, old_name: str, new_name: str) -> str:
    """rename a variable (assignments and references). scope-aware."""
    tree = ast.parse(source)

    class VarRenamer(ast.NodeTransformer):
        def visit_Name(self, node):
            if node.id == old_name:
                node.id = new_name
            return node

        def visit_arg(self, node):
            if node.arg == old_name:
                node.arg = new_name
            return node

    tree = VarRenamer().visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + "\n"


# ============================================================
# EXTRACT
# ============================================================

def extract_function(source: str, start_line: int, end_line: int,
                     func_name: str) -> str:
    """extract lines into a new function, replace with a call.

    auto-detects parameters from variables used in the extracted block
    that were defined before it.
    """
    lines = source.splitlines()

    if start_line < 1 or end_line > len(lines) or start_line > end_line:
        return source

    extracted = lines[start_line - 1:end_line]

    # detect indentation
    first_indent = len(extracted[0]) - len(extracted[0].lstrip())
    base_indent = " " * first_indent

    # find variables
    used = _names_in_lines(extracted)
    defined_before = _assigned_in_lines(lines[:start_line - 1])
    defined_in = _assigned_in_lines(extracted)
    used_after = _names_in_lines(lines[end_line:])

    params = sorted(used & defined_before)
    returns = sorted(defined_in & used_after)

    # build new function
    dedented = [line[first_indent:] if len(line) >= first_indent else line
                for line in extracted]
    param_str = ", ".join(params)
    func_lines = [f"def {func_name}({param_str}):"]
    for line in dedented:
        func_lines.append(f"    {line}" if line.strip() else "")
    if returns:
        func_lines.append(f"    return {', '.join(returns)}")

    # build the call
    if returns:
        ret_str = ", ".join(returns)
        call_line = f"{base_indent}{ret_str} = {func_name}({param_str})"
    else:
        call_line = f"{base_indent}{func_name}({param_str})"

    # rebuild
    result = lines[:start_line - 1]
    result.append(call_line)
    result.extend(lines[end_line:])

    # insert new function before the block
    for i, fl in enumerate(func_lines):
        result.insert(start_line - 1 + i, fl)
    result.insert(start_line - 1 + len(func_lines), "")

    return "\n".join(result) + "\n"


# ============================================================
# DECORATORS
# ============================================================

def add_decorator(source: str, func_name: str, decorator: str) -> str:
    """add a decorator above a function or class definition."""
    lines = source.splitlines(keepends=True)
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == func_name:
                # check if already has this decorator
                for d in node.decorator_list:
                    if isinstance(d, ast.Name) and d.id == decorator.lstrip("@"):
                        return source
                    if isinstance(d, ast.Attribute):
                        dec_str = ast.unparse(d)
                        if dec_str == decorator.lstrip("@"):
                            return source

                # find the line to insert before (first decorator or def line)
                if node.decorator_list:
                    insert_line = node.decorator_list[0].lineno - 1
                else:
                    insert_line = node.lineno - 1

                indent = len(lines[insert_line]) - len(lines[insert_line].lstrip())
                prefix = " " * indent
                dec_text = decorator if decorator.startswith("@") else f"@{decorator}"
                new_line = f"{prefix}{dec_text}\n"
                return "".join(lines[:insert_line]) + new_line + "".join(lines[insert_line:])

    return source


def remove_decorator(source: str, func_name: str, decorator: str) -> str:
    """remove a specific decorator from a function or class."""
    lines = source.splitlines(keepends=True)
    tree = ast.parse(source)
    bare = decorator.lstrip("@")

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == func_name:
                for d in node.decorator_list:
                    dec_str = ""
                    if isinstance(d, ast.Name):
                        dec_str = d.id
                    elif isinstance(d, ast.Attribute):
                        dec_str = ast.unparse(d)
                    elif isinstance(d, ast.Call):
                        dec_str = ast.unparse(d.func)

                    if dec_str == bare:
                        start = d.lineno - 1
                        end = d.end_lineno
                        return "".join(lines[:start]) + "".join(lines[end:])

    return source


# ============================================================
# TYPE HINTS
# ============================================================

def add_type_hints(source: str) -> str:
    """add basic type hints where they can be inferred. conservative."""
    tree = ast.parse(source)

    class HintAdder(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            self.generic_visit(node)
            if node.returns is None and _returns_none(node):
                node.returns = ast.Constant(value=None)
            return node

        def visit_AnnAssign(self, node):
            return node  # already annotated, skip

        def visit_Assign(self, node):
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                hint = _infer_type(node.value)
                if hint:
                    target = node.targets[0]
                    ann = ast.AnnAssign(
                        target=target,
                        annotation=ast.Name(id=hint, ctx=ast.Load()),
                        value=node.value,
                        simple=1,
                    )
                    return ast.copy_location(ann, node)
            return node

    tree = HintAdder().visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + "\n"


# ============================================================
# LISTING
# ============================================================

def list_functions(source: str) -> list[dict]:
    """list all function definitions with metadata."""
    tree = ast.parse(source)
    result = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in node.args.args if a.arg not in ("self", "cls")]
            decorators = []
            for d in node.decorator_list:
                if isinstance(d, ast.Name):
                    decorators.append(d.id)
                else:
                    decorators.append(ast.unparse(d))

            returns = None
            if node.returns:
                returns = ast.unparse(node.returns)

            result.append({
                "name": node.name,
                "line": node.lineno,
                "args": args,
                "decorators": decorators,
                "returns": returns,
            })

    return result


def list_classes(source: str) -> list[dict]:
    """list all class definitions with metadata."""
    tree = ast.parse(source)
    result = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            bases = [ast.unparse(b) for b in node.bases]
            methods = []
            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(item.name)

            decorators = []
            for d in node.decorator_list:
                if isinstance(d, ast.Name):
                    decorators.append(d.id)
                else:
                    decorators.append(ast.unparse(d))

            result.append({
                "name": node.name,
                "line": node.lineno,
                "bases": bases,
                "methods": methods,
                "decorators": decorators,
            })

    return result


# ============================================================
# HELPERS
# ============================================================

def _last_import_line(tree: ast.Module) -> int:
    """line index (0-based) after the last import statement."""
    last = 0
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            last = node.end_lineno
    return last


def _after_docstring(lines: list[str]) -> int:
    """line index after module docstring and comments."""
    i = 0
    # skip blank lines and comments
    while i < len(lines) and (not lines[i].strip() or lines[i].strip().startswith("#")):
        i += 1
    # skip docstring
    if i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith(('"""', "'''")):
            quote = stripped[:3]
            if stripped.count(quote) >= 2:
                i += 1
            else:
                i += 1
                while i < len(lines) and quote not in lines[i]:
                    i += 1
                if i < len(lines):
                    i += 1
    return i


def _attr_root(node: ast.Attribute) -> Optional[str]:
    """get the root name of a chained attribute access."""
    while isinstance(node, ast.Attribute):
        node = node.value
    if isinstance(node, ast.Name):
        return node.id
    return None


def _names_in_lines(lines: list[str]) -> set[str]:
    """find identifier names used in lines. simple heuristic."""
    names = set()
    for line in lines:
        tokens = re.findall(r'\b([a-zA-Z_]\w*)\b', line)
        names.update(tokens)
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


def _assigned_in_lines(lines: list[str]) -> set[str]:
    """find variable names assigned in lines."""
    names = set()
    for line in lines:
        stripped = line.strip()
        match = re.match(r'^([a-zA-Z_]\w*)\s*=', stripped)
        if match and not stripped.startswith(('def ', 'class ')):
            names.add(match.group(1))
        match = re.match(r'^for\s+(\w+)', stripped)
        if match:
            names.add(match.group(1))
    return names


def _returns_none(node: ast.FunctionDef) -> bool:
    """check if a function never returns a value (only bare return or no return)."""
    for child in ast.walk(node):
        if isinstance(child, ast.Return) and child.value is not None:
            return False
        if isinstance(child, ast.Yield) or isinstance(child, ast.YieldFrom):
            return False
    return True


def _infer_type(node: ast.expr) -> Optional[str]:
    """infer type from a literal value. conservative, returns None if unsure."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return "bool"
        if isinstance(node.value, int):
            return "int"
        if isinstance(node.value, str):
            return "str"
        if isinstance(node.value, float):
            return "float"
    return None
