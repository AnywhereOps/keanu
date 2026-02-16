"""migrate.py - database migration helpers.

generate migrations from model changes, track migration history,
detect schema drift. works with raw SQL, Alembic, and Django-style.

in the world: the map of every change the foundation has ever seen.
when the ground shifts, this is how you know what moved.
"""

import hashlib
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Migration:
    """a single migration."""
    id: str
    name: str
    sql_up: str
    sql_down: str = ""
    created_at: float = 0.0
    applied: bool = False

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()


@dataclass
class MigrationPlan:
    """a plan for migrating between schema states."""
    steps: list[Migration] = field(default_factory=list)
    source: str = ""  # where the plan came from

    @property
    def sql(self) -> str:
        return "\n\n".join(m.sql_up for m in self.steps)


# ============================================================
# MIGRATION GENERATION
# ============================================================

def generate_create_table(table_name: str, columns: dict[str, str]) -> str:
    """generate a CREATE TABLE statement.

    columns: {name: type_with_constraints}
    """
    col_defs = []
    for name, typedef in columns.items():
        col_defs.append(f"    {name} {typedef}")

    return f"CREATE TABLE {table_name} (\n{','.join(chr(10) + c for c in col_defs)}\n);"


def generate_add_column(table: str, column: str, typedef: str) -> str:
    """generate an ALTER TABLE ADD COLUMN statement."""
    return f"ALTER TABLE {table} ADD COLUMN {column} {typedef};"


def generate_drop_column(table: str, column: str) -> str:
    """generate an ALTER TABLE DROP COLUMN statement."""
    return f"ALTER TABLE {table} DROP COLUMN {column};"


def generate_create_index(table: str, columns: list[str],
                          unique: bool = False, name: str = "") -> str:
    """generate a CREATE INDEX statement."""
    idx_name = name or f"idx_{table}_{'_'.join(columns)}"
    unique_str = "UNIQUE " if unique else ""
    cols = ", ".join(columns)
    return f"CREATE {unique_str}INDEX {idx_name} ON {table} ({cols});"


def generate_rename_column(table: str, old_name: str, new_name: str) -> str:
    """generate an ALTER TABLE RENAME COLUMN statement."""
    return f"ALTER TABLE {table} RENAME COLUMN {old_name} TO {new_name};"


# ============================================================
# DIFF-BASED MIGRATION
# ============================================================

@dataclass
class SchemaDiff:
    """difference between two schema states."""
    added_tables: list[str] = field(default_factory=list)
    dropped_tables: list[str] = field(default_factory=list)
    added_columns: list[tuple[str, str, str]] = field(default_factory=list)  # (table, col, type)
    dropped_columns: list[tuple[str, str]] = field(default_factory=list)    # (table, col)
    modified_columns: list[tuple[str, str, str, str]] = field(default_factory=list)  # (table, col, old, new)

    @property
    def has_changes(self) -> bool:
        return bool(
            self.added_tables or self.dropped_tables or
            self.added_columns or self.dropped_columns or
            self.modified_columns
        )


def diff_schemas(old_tables: dict, new_tables: dict) -> SchemaDiff:
    """compare two schema representations and find differences.

    old_tables, new_tables: {table_name: {col_name: col_type}}
    """
    diff = SchemaDiff()

    old_names = set(old_tables.keys())
    new_names = set(new_tables.keys())

    diff.added_tables = sorted(new_names - old_names)
    diff.dropped_tables = sorted(old_names - new_names)

    # compare columns in shared tables
    for table in old_names & new_names:
        old_cols = old_tables[table]
        new_cols = new_tables[table]

        old_col_names = set(old_cols.keys())
        new_col_names = set(new_cols.keys())

        for col in sorted(new_col_names - old_col_names):
            diff.added_columns.append((table, col, new_cols[col]))

        for col in sorted(old_col_names - new_col_names):
            diff.dropped_columns.append((table, col))

        for col in sorted(old_col_names & new_col_names):
            if old_cols[col] != new_cols[col]:
                diff.modified_columns.append((table, col, old_cols[col], new_cols[col]))

    return diff


def diff_to_sql(diff: SchemaDiff) -> str:
    """convert a schema diff into SQL migration statements."""
    statements = []

    for table in diff.added_tables:
        statements.append(f"-- TODO: CREATE TABLE {table} (define columns)")

    for table in diff.dropped_tables:
        statements.append(f"DROP TABLE IF EXISTS {table};")

    for table, col, typedef in diff.added_columns:
        statements.append(generate_add_column(table, col, typedef))

    for table, col in diff.dropped_columns:
        statements.append(generate_drop_column(table, col))

    for table, col, old_type, new_type in diff.modified_columns:
        statements.append(f"-- {table}.{col}: {old_type} -> {new_type}")
        statements.append(f"ALTER TABLE {table} ALTER COLUMN {col} TYPE {new_type};")

    return "\n".join(statements)


# ============================================================
# MIGRATION FILE MANAGEMENT
# ============================================================

def create_migration_file(name: str, sql_up: str, sql_down: str = "",
                          migrations_dir: str = "migrations") -> str:
    """create a new migration file."""
    mig_dir = Path(migrations_dir)
    mig_dir.mkdir(parents=True, exist_ok=True)

    # find next sequence number
    existing = sorted(mig_dir.glob("*.sql"))
    seq = len(existing) + 1

    # sanitize name
    safe_name = re.sub(r'[^a-z0-9_]', '_', name.lower())
    filename = f"{seq:04d}_{safe_name}.sql"
    filepath = mig_dir / filename

    content = f"-- Migration: {name}\n"
    content += f"-- Created: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    content += "-- Up\n"
    content += sql_up + "\n"

    if sql_down:
        content += "\n-- Down\n"
        content += sql_down + "\n"

    filepath.write_text(content)
    return str(filepath)


def list_migrations(migrations_dir: str = "migrations") -> list[dict]:
    """list all migration files in order."""
    mig_dir = Path(migrations_dir)
    if not mig_dir.is_dir():
        return []

    migrations = []
    for f in sorted(mig_dir.glob("*.sql")):
        content = f.read_text()
        hash_val = hashlib.sha256(content.encode()).hexdigest()[:12]
        migrations.append({
            "file": f.name,
            "path": str(f),
            "hash": hash_val,
            "size": len(content),
        })

    return migrations


def parse_migration_file(path: str) -> Migration:
    """parse a migration file into up/down SQL."""
    content = Path(path).read_text()
    name = Path(path).stem

    # split on "-- Down" marker
    parts = re.split(r'--\s*Down\s*\n', content, maxsplit=1)
    sql_up = parts[0]
    sql_down = parts[1] if len(parts) > 1 else ""

    # clean up: remove comment headers from up section
    up_lines = []
    for line in sql_up.split("\n"):
        if line.startswith("-- Migration:") or line.startswith("-- Created:") or line.strip() == "-- Up":
            continue
        up_lines.append(line)
    sql_up = "\n".join(up_lines).strip()

    return Migration(
        id=name,
        name=name,
        sql_up=sql_up,
        sql_down=sql_down.strip(),
    )


# ============================================================
# ALEMBIC DETECTION
# ============================================================

def detect_migration_system(root: str = ".") -> str:
    """detect which migration system is in use."""
    root_path = Path(root)

    if (root_path / "alembic.ini").exists() or (root_path / "alembic").is_dir():
        return "alembic"
    if (root_path / "migrations").is_dir():
        # check for Django-style
        if any((root_path / "migrations").glob("*.py")):
            return "django"
        if any((root_path / "migrations").glob("*.sql")):
            return "raw_sql"
    if (root_path / "db" / "migrate").is_dir():
        return "rails"
    if (root_path / "prisma").is_dir():
        return "prisma"

    return "none"


def migration_status(root: str = ".") -> dict:
    """get migration system status."""
    system = detect_migration_system(root)

    if system == "none":
        return {"system": "none", "migrations": 0}

    root_path = Path(root)
    count = 0

    if system == "alembic":
        alembic_dir = root_path / "alembic" / "versions"
        if alembic_dir.is_dir():
            count = sum(1 for f in alembic_dir.glob("*.py"))
    elif system == "django":
        count = sum(1 for f in (root_path / "migrations").glob("*.py")
                    if f.name != "__init__.py")
    elif system == "raw_sql":
        count = sum(1 for f in (root_path / "migrations").glob("*.sql"))
    elif system == "rails":
        count = sum(1 for f in (root_path / "db" / "migrate").glob("*.rb"))
    elif system == "prisma":
        prisma_dir = root_path / "prisma" / "migrations"
        if prisma_dir.is_dir():
            count = sum(1 for d in prisma_dir.iterdir() if d.is_dir())

    return {
        "system": system,
        "migrations": count,
    }
