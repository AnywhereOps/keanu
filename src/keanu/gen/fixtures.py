"""fixtures.py - generate test fixtures and fake data.

fake names, emails, phones, addresses, dates, text, json, csv, sql.
pure stdlib. no external deps. seed() for reproducibility.

in the world: ash for testing. no fire needed, just structured noise.
"""

import csv
import io
import json
import random
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

# ---------------------------------------------------------------------------
# built-in data lists
# ---------------------------------------------------------------------------

FIRST_NAMES = [
    "Alice", "Bob", "Charlie", "Dana", "Eve", "Frank", "Grace", "Hank",
    "Iris", "Jack", "Karen", "Leo", "Mia", "Noah", "Olive", "Paul",
    "Quinn", "Rosa", "Sam", "Tina", "Uma", "Victor", "Wendy", "Xander",
    "Yara", "Zane",
]

LAST_NAMES = [
    "Adams", "Baker", "Chen", "Davis", "Evans", "Foster", "Garcia", "Hill",
    "Ito", "Jones", "Kim", "Lopez", "Miller", "Nguyen", "Owens", "Patel",
    "Quinn", "Rivera", "Smith", "Torres", "Ueda", "Vega", "Wang", "Xu",
    "Young", "Zhang",
]

STREETS = [
    "123 Main St", "456 Oak Ave", "789 Pine Rd", "101 Maple Dr",
    "202 Elm Ln", "303 Cedar Blvd", "404 Birch Way", "505 Walnut Ct",
    "606 Spruce Pl", "707 Ash St",
]

CITIES = [
    "Springfield", "Portland", "Austin", "Denver", "Raleigh",
    "Madison", "Boise", "Tucson", "Omaha", "Richmond",
]

STATES = [
    "CA", "TX", "NY", "FL", "IL", "PA", "OH", "GA", "NC", "MI",
]

LOREM_WORDS = [
    "lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing",
    "elit", "sed", "do", "eiusmod", "tempor", "incididunt", "ut", "labore",
    "et", "dolore", "magna", "aliqua", "enim", "ad", "minim", "veniam",
    "quis", "nostrud", "exercitation", "ullamco", "laboris", "nisi",
    "aliquip", "ex", "ea", "commodo", "consequat",
]

EMAIL_DOMAINS = [
    "example.com", "test.org", "mail.net", "demo.io", "fake.dev",
]

_rng = random.Random()


# ---------------------------------------------------------------------------
# seed
# ---------------------------------------------------------------------------

def seed(n: int = 42):
    """set random seed for reproducible output."""
    _rng.seed(n)


# ---------------------------------------------------------------------------
# fake generators
# ---------------------------------------------------------------------------

def fake_name() -> str:
    """random full name from built-in lists."""
    return f"{_rng.choice(FIRST_NAMES)} {_rng.choice(LAST_NAMES)}"


def fake_email(name: str = "") -> str:
    """email from name or random."""
    if not name:
        name = fake_name()
    parts = name.lower().split()
    local = ".".join(parts)
    domain = _rng.choice(EMAIL_DOMAINS)
    return f"{local}@{domain}"


def fake_phone() -> str:
    """US phone format."""
    area = _rng.randint(200, 999)
    mid = _rng.randint(200, 999)
    last = _rng.randint(1000, 9999)
    return f"({area}) {mid}-{last}"


def fake_address() -> dict:
    """random US address dict."""
    return {
        "street": _rng.choice(STREETS),
        "city": _rng.choice(CITIES),
        "state": _rng.choice(STATES),
        "zip": f"{_rng.randint(10000, 99999)}",
    }


def fake_uuid() -> str:
    """uuid4 string."""
    return str(uuid.UUID(int=_rng.getrandbits(128), version=4))


def fake_date(start: str = "2020-01-01", end: str = "2026-12-31") -> str:
    """ISO date in range."""
    d0 = date.fromisoformat(start)
    d1 = date.fromisoformat(end)
    delta = (d1 - d0).days
    if delta <= 0:
        return start
    offset = _rng.randint(0, delta)
    return (d0 + timedelta(days=offset)).isoformat()


def fake_text(words: int = 10) -> str:
    """lorem ipsum style sentence."""
    picked = [_rng.choice(LOREM_WORDS) for _ in range(words)]
    picked[0] = picked[0].capitalize()
    return " ".join(picked) + "."


def fake_int(low: int = 0, high: int = 1000) -> int:
    """random int in range."""
    return _rng.randint(low, high)


def fake_choice(options: list) -> Any:
    """pick one from a list."""
    return _rng.choice(options)


def fake_bool(true_pct: float = 0.5) -> bool:
    """random bool with configurable true percentage."""
    return _rng.random() < true_pct


# ---------------------------------------------------------------------------
# type dispatch (used by fake_json, fake_csv, fake_sql_inserts)
# ---------------------------------------------------------------------------

_TYPE_MAP = {
    "string": lambda: fake_text(3),
    "str": lambda: fake_text(3),
    "int": lambda: fake_int(),
    "float": lambda: round(_rng.uniform(0, 1000), 2),
    "bool": lambda: fake_bool(),
    "email": lambda: fake_email(),
    "name": lambda: fake_name(),
    "date": lambda: fake_date(),
    "uuid": lambda: fake_uuid(),
    "phone": lambda: fake_phone(),
    "text": lambda: fake_text(),
}


def _generate_value(spec: Any) -> Any:
    """generate a value from a type spec (string, list, or dict)."""
    if isinstance(spec, str):
        gen = _TYPE_MAP.get(spec)
        if gen is None:
            return spec
        return gen()
    if isinstance(spec, list) and len(spec) == 1:
        count = _rng.randint(1, 5)
        return [_generate_value(spec[0]) for _ in range(count)]
    if isinstance(spec, dict):
        return {k: _generate_value(v) for k, v in spec.items()}
    return spec


# ---------------------------------------------------------------------------
# structured generators
# ---------------------------------------------------------------------------

def fake_json(schema: dict) -> dict:
    """generate fake data matching a simple schema.

    schema format: {"field": "type"} where type is string, int, float,
    bool, email, name, date, uuid, phone, text. also supports
    {"field": ["type"]} for lists and {"field": {"nested": "type"}}
    for nested objects.
    """
    return {k: _generate_value(v) for k, v in schema.items()}


def fake_csv(columns: list[dict], rows: int = 10) -> str:
    """generate CSV string. each column: {"name": str, "type": str}."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    headers = [c["name"] for c in columns]
    types = [c["type"] for c in columns]
    writer.writerow(headers)
    for _ in range(rows):
        row = [_generate_value(t) for t in types]
        writer.writerow(row)
    return buf.getvalue()


def fake_sql_inserts(table: str, columns: list[dict], rows: int = 10) -> str:
    """generate INSERT statements."""
    col_names = [c["name"] for c in columns]
    types = [c["type"] for c in columns]
    header = f"INSERT INTO {table} ({', '.join(col_names)}) VALUES"
    lines = []
    for _ in range(rows):
        vals = []
        for t in types:
            v = _generate_value(t)
            if isinstance(v, bool):
                vals.append("TRUE" if v else "FALSE")
            elif isinstance(v, (int, float)):
                vals.append(str(v))
            else:
                escaped = str(v).replace("'", "''")
                vals.append(f"'{escaped}'")
        lines.append(f"{header} ({', '.join(vals)});")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Fixture dataclass + save/load
# ---------------------------------------------------------------------------

@dataclass
class Fixture:
    """named collection of generated rows."""
    name: str
    data: list[dict] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)


def save_fixture(fixture: Fixture, path: str, fmt: str = "json"):
    """save fixture as json or csv."""
    if fmt == "json":
        payload = {
            "name": fixture.name,
            "columns": fixture.columns,
            "data": fixture.data,
        }
        with open(path, "w") as f:
            json.dump(payload, f, indent=2)
    elif fmt == "csv":
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fixture.columns)
            writer.writeheader()
            for row in fixture.data:
                writer.writerow(row)
    else:
        raise ValueError(f"unsupported format: {fmt}")


def load_fixture(path: str) -> Fixture:
    """load fixture from json or csv."""
    if path.endswith(".json"):
        with open(path) as f:
            payload = json.load(f)
        return Fixture(
            name=payload.get("name", ""),
            columns=payload.get("columns", []),
            data=payload.get("data", []),
        )
    elif path.endswith(".csv"):
        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        cols = list(rows[0].keys()) if rows else []
        name = path.rsplit("/", 1)[-1].replace(".csv", "")
        return Fixture(name=name, columns=cols, data=rows)
    else:
        raise ValueError(f"unsupported file extension: {path}")
