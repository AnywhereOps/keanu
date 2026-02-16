"""structfile.py - parse and write structured config files.

handles TOML, INI, .env, and simple YAML. pure python, no external deps.
used by config.py, project.py, and environment detection.

in the world: config files are the bones of a project. this reads them
without pulling in a forest of dependencies.
"""

import re
from pathlib import Path


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _strip_comment(line: str, comment_chars: str = "#") -> str:
    """remove trailing comment, respecting quotes."""
    in_quote = None
    for i, ch in enumerate(line):
        if ch in ('"', "'") and not in_quote:
            in_quote = ch
        elif ch == in_quote:
            in_quote = None
        elif ch in comment_chars and not in_quote:
            return line[:i].rstrip()
    return line.rstrip()


def _parse_value(raw: str):
    """coerce a string value to int, float, bool, or leave as str."""
    if raw in ("true", "True"):
        return True
    if raw in ("false", "False"):
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _unquote(s: str) -> str:
    """strip matching quotes from a string value."""
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    return s


def _set_dotted(d: dict, keys: list[str], value):
    """set a value in a nested dict via dotted key path."""
    for k in keys[:-1]:
        if k not in d:
            d[k] = {}
        d = d[k]
    d[keys[-1]] = value


# ---------------------------------------------------------------------------
# TOML
# ---------------------------------------------------------------------------

def _parse_toml_value(raw: str):
    """parse a TOML value string (after the =)."""
    raw = raw.strip()
    if not raw:
        return ""

    # strings
    if raw.startswith('"""'):
        end = raw.find('"""', 3)
        if end != -1:
            return raw[3:end]
        return raw[3:]
    if raw[0] in ('"', "'"):
        return _unquote(raw)

    # booleans
    if raw == "true":
        return True
    if raw == "false":
        return False

    # arrays
    if raw.startswith("["):
        return _parse_toml_array(raw)

    # inline tables
    if raw.startswith("{"):
        return _parse_toml_inline_table(raw)

    # numbers
    try:
        if "." in raw or "e" in raw.lower():
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def _parse_toml_array(raw: str) -> list:
    """parse a TOML array literal."""
    inner = raw.strip()[1:-1].strip()
    if not inner:
        return []
    items = []
    current = ""
    depth = 0
    in_quote = None
    for ch in inner:
        if ch in ('"', "'") and not in_quote:
            in_quote = ch
            current += ch
        elif ch == in_quote:
            in_quote = None
            current += ch
        elif in_quote:
            current += ch
        elif ch == "[":
            depth += 1
            current += ch
        elif ch == "]":
            depth -= 1
            current += ch
        elif ch == "," and depth == 0:
            items.append(_parse_toml_value(current.strip()))
            current = ""
        else:
            current += ch
    if current.strip():
        items.append(_parse_toml_value(current.strip()))
    return items


def _parse_toml_inline_table(raw: str) -> dict:
    """parse a TOML inline table like {key = val, key2 = val2}."""
    inner = raw.strip()[1:-1].strip()
    if not inner:
        return {}
    result = {}
    for pair in _split_toml_pairs(inner):
        pair = pair.strip()
        if "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        result[k.strip()] = _parse_toml_value(v.strip())
    return result


def _split_toml_pairs(s: str) -> list[str]:
    """split comma-separated pairs, respecting nesting."""
    parts = []
    current = ""
    depth = 0
    in_quote = None
    for ch in s:
        if ch in ('"', "'") and not in_quote:
            in_quote = ch
        elif ch == in_quote:
            in_quote = None
        elif not in_quote:
            if ch in ("[", "{"):
                depth += 1
            elif ch in ("]", "}"):
                depth -= 1
            elif ch == "," and depth == 0:
                parts.append(current)
                current = ""
                continue
        current += ch
    if current.strip():
        parts.append(current)
    return parts


def parse_toml(text: str) -> dict:
    """parse TOML text into a nested dict."""
    result = {}
    current_table = result
    current_path: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        # table header [section] or [section.sub]
        m = re.match(r"^\[([^\[\]]+)\]\s*$", line)
        if m:
            path = [k.strip().strip('"') for k in m.group(1).split(".")]
            current_path = path
            current_table = result
            for k in path:
                if k not in current_table:
                    current_table[k] = {}
                current_table = current_table[k]
            continue

        # array of tables [[section]]
        m = re.match(r"^\[\[([^\[\]]+)\]\]\s*$", line)
        if m:
            path = [k.strip().strip('"') for k in m.group(1).split(".")]
            current_path = path
            parent = result
            for k in path[:-1]:
                if k not in parent:
                    parent[k] = {}
                parent = parent[k]
            key = path[-1]
            if key not in parent:
                parent[key] = []
            new_table = {}
            parent[key].append(new_table)
            current_table = new_table
            continue

        # key = value (supports dotted keys)
        m = re.match(r"^([a-zA-Z0-9._\"-]+)\s*=\s*(.*)$", line)
        if m:
            key_raw = m.group(1).strip()
            val_raw = _strip_comment(m.group(2), "#")
            keys = [k.strip().strip('"') for k in key_raw.split(".")]
            value = _parse_toml_value(val_raw)
            if len(keys) == 1:
                current_table[keys[0]] = value
            else:
                _set_dotted(current_table, keys, value)

    return result


def write_toml(data: dict) -> str:
    """serialize a dict to TOML string."""
    lines = []
    tables = []

    for key, val in data.items():
        if isinstance(val, dict):
            tables.append((key, val))
        elif isinstance(val, list) and val and isinstance(val[0], dict):
            tables.append((key, val))
        else:
            lines.append(f"{key} = {_toml_encode(val)}")

    if lines:
        lines.append("")

    for key, val in tables:
        if isinstance(val, list):
            for item in val:
                lines.append(f"[[{key}]]")
                for k, v in item.items():
                    lines.append(f"{k} = {_toml_encode(v)}")
                lines.append("")
        else:
            lines.append(f"[{key}]")
            for k, v in val.items():
                if isinstance(v, dict):
                    # nested table: section.subsection
                    lines.append(f"\n[{key}.{k}]")
                    for k2, v2 in v.items():
                        lines.append(f"{k2} = {_toml_encode(v2)}")
                else:
                    lines.append(f"{k} = {_toml_encode(v)}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _toml_encode(val) -> str:
    """encode a single value as TOML."""
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        return str(val)
    if isinstance(val, str):
        return f'"{val}"'
    if isinstance(val, list):
        items = ", ".join(_toml_encode(v) for v in val)
        return f"[{items}]"
    if isinstance(val, dict):
        pairs = ", ".join(f"{k} = {_toml_encode(v)}" for k, v in val.items())
        return f"{{{pairs}}}"
    return f'"{val}"'


# ---------------------------------------------------------------------------
# INI
# ---------------------------------------------------------------------------

def parse_ini(text: str) -> dict:
    """parse INI/cfg text into a nested dict."""
    result = {}
    current_section = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line[0] in ("#", ";"):
            continue

        m = re.match(r"^\[([^\]]+)\]\s*$", line)
        if m:
            current_section = m.group(1).strip()
            if current_section not in result:
                result[current_section] = {}
            continue

        line = _strip_comment(line, "#;")
        m = re.match(r"^([^=:]+)[=:](.*)$", line)
        if m:
            key = m.group(1).strip()
            val = m.group(2).strip()
            val = _unquote(val)
            val = _parse_value(val)
            if current_section:
                result[current_section][key] = val
            else:
                result[key] = val

    return result


def write_ini(data: dict) -> str:
    """serialize a dict to INI string."""
    lines = []
    top_level = []
    sections = []

    for key, val in data.items():
        if isinstance(val, dict):
            sections.append((key, val))
        else:
            top_level.append((key, val))

    for key, val in top_level:
        lines.append(f"{key} = {val}")

    if top_level and sections:
        lines.append("")

    for name, section in sections:
        lines.append(f"[{name}]")
        for key, val in section.items():
            lines.append(f"{key} = {val}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# .env
# ---------------------------------------------------------------------------

def parse_env(text: str) -> dict:
    """parse .env file into a flat dict."""
    result = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        # strip optional export prefix
        if line.startswith("export "):
            line = line[7:].strip()

        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)", line)
        if not m:
            continue
        key = m.group(1)
        val = m.group(2).strip()
        val = _unquote(val)
        result[key] = val

    return result


def write_env(data: dict) -> str:
    """serialize a dict to .env string."""
    lines = []
    for key, val in data.items():
        val_str = str(val)
        if " " in val_str or "=" in val_str or '"' in val_str:
            val_str = f'"{val_str}"'
        lines.append(f"{key}={val_str}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# simple YAML
# ---------------------------------------------------------------------------

def parse_yaml_simple(text: str) -> dict:
    """parse simple YAML into a dict. flat keys, lists, one level nesting."""
    result = {}
    current_key = None
    current_list = None

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip())

        # list item under a key
        if stripped.startswith("- "):
            item = stripped[2:].strip()
            item = _unquote(item)
            if current_list is not None:
                current_list.append(item)
            continue

        # key: value
        m = re.match(r"^([a-zA-Z0-9_][a-zA-Z0-9_./-]*)\s*:\s*(.*)", stripped)
        if m:
            key = m.group(1)
            val = m.group(2).strip()

            if indent > 0 and current_key:
                # nested under current_key
                if not isinstance(result.get(current_key), dict):
                    result[current_key] = {}
                current_list = None
                if val:
                    result[current_key][key] = _yaml_value(val)
                else:
                    result[current_key][key] = None
                continue

            current_list = None
            if val:
                parsed = _yaml_value(val)
                result[key] = parsed
                current_key = key
            else:
                # could be start of a list or nested block
                result[key] = None
                current_key = key
                current_list = []
                result[key] = current_list
            continue

    # clean up empty lists that should be None
    for k, v in list(result.items()):
        if isinstance(v, list) and not v:
            result[k] = None

    return result


def _yaml_value(raw: str):
    """parse a simple YAML scalar value."""
    raw = _strip_comment(raw, "#")
    raw = raw.strip()
    if not raw:
        return None
    if raw in ("true", "True", "yes", "on"):
        return True
    if raw in ("false", "False", "no", "off"):
        return False
    if raw == "null" or raw == "~":
        return None
    raw_unq = _unquote(raw)
    if raw_unq != raw:
        return raw_unq
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


# ---------------------------------------------------------------------------
# format detection and dispatch
# ---------------------------------------------------------------------------

_EXT_MAP = {
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".env": "env",
    ".yaml": "yaml",
    ".yml": "yaml",
}


def detect_format(path: str) -> str:
    """detect config format from file extension."""
    p = Path(path)
    name = p.name.lower()
    if name == ".env" or name.startswith(".env"):
        return "env"
    ext = p.suffix.lower()
    return _EXT_MAP.get(ext, "unknown")


_PARSERS = {
    "toml": parse_toml,
    "ini": parse_ini,
    "env": parse_env,
    "yaml": parse_yaml_simple,
}


def parse_file(path: str) -> dict:
    """auto-detect format and parse a config file."""
    fmt = detect_format(path)
    parser = _PARSERS.get(fmt)
    if not parser:
        raise ValueError(f"unknown config format for {path}")
    text = Path(path).read_text()
    return parser(text)


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------

def merge_configs(base: dict, overlay: dict) -> dict:
    """deep merge two config dicts. overlay wins on conflicts."""
    result = dict(base)
    for key, val in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = merge_configs(result[key], val)
        else:
            result[key] = val
    return result
