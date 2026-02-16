"""io.py - JSON and JSONL utilities.

read_json, write_json, read_jsonl, append_jsonl.
used by memberberry, gitstore, miss_tracker, abilities, codec.
"""

import json
from pathlib import Path

from keanu.paths import ensure_dir


def read_json(path: Path, default=None):
    """read a JSON file. returns default if missing or corrupt."""
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return default


def write_json(path: Path, data, indent: int = 2):
    """write data as JSON. creates parent dirs."""
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, indent=indent, ensure_ascii=False))


def read_jsonl(path: Path) -> list[dict]:
    """read a JSONL file. skips blank/corrupt lines."""
    if not path.exists():
        return []
    records = []
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return records


def append_jsonl(path: Path, record: dict):
    """append one record to a JSONL file. creates parent dirs."""
    ensure_dir(path.parent)
    with open(path, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
