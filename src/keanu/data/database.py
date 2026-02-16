"""database.py - database awareness.

parse SQL migrations, detect schema, analyze queries,
generate models from schema. no LLM needed for analysis.

in the world: the cartographer of data. maps the territory of tables and columns.
"""

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Column:
    """a database column."""
    name: str
    type: str
    nullable: bool = True
    primary_key: bool = False
    default: str = ""
    references: str = ""  # "table.column" for foreign keys


@dataclass
class Table:
    """a database table."""
    name: str
    columns: list[Column] = field(default_factory=list)
    indexes: list[str] = field(default_factory=list)

    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    def primary_keys(self) -> list[str]:
        return [c.name for c in self.columns if c.primary_key]

    def foreign_keys(self) -> list[tuple[str, str]]:
        return [(c.name, c.references) for c in self.columns if c.references]


@dataclass
class Schema:
    """a database schema."""
    tables: list[Table] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)

    def table_names(self) -> list[str]:
        return [t.name for t in self.tables]

    def get_table(self, name: str) -> Table | None:
        for t in self.tables:
            if t.name == name:
                return t
        return None

    def relationships(self) -> list[dict]:
        """find all foreign key relationships."""
        rels = []
        for table in self.tables:
            for col in table.columns:
                if col.references:
                    parts = col.references.split(".")
                    if len(parts) == 2:
                        rels.append({
                            "from_table": table.name,
                            "from_column": col.name,
                            "to_table": parts[0],
                            "to_column": parts[1],
                        })
        return rels


# ============================================================
# SQL PARSING
# ============================================================

def parse_sql(sql: str) -> Schema:
    """parse SQL DDL statements into a Schema."""
    tables = []
    # find CREATE TABLE statements - match balanced parens
    for match in re.finditer(
        r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?["`]?(\w+)["`]?\s*\(',
        sql, re.IGNORECASE,
    ):
        table_name = match.group(1)
        start = match.end()
        body = _extract_balanced_parens(sql, start)
        if body is None:
            continue
        columns = _parse_columns(body)
        tables.append(Table(name=table_name, columns=columns))

    # find CREATE INDEX statements
    for match in re.finditer(
        r'CREATE\s+(?:UNIQUE\s+)?INDEX\s+\w+\s+ON\s+["`]?(\w+)["`]?',
        sql, re.IGNORECASE,
    ):
        table_name = match.group(1)
        for t in tables:
            if t.name == table_name:
                t.indexes.append(match.group(0).strip())

    return Schema(tables=tables)


def parse_migration_dir(dirpath: str) -> Schema:
    """parse all SQL files in a migrations directory."""
    path = Path(dirpath)
    if not path.is_dir():
        return Schema()

    schema = Schema()
    files = sorted(path.glob("*.sql"))
    for f in files:
        try:
            sql = f.read_text()
            sub_schema = parse_sql(sql)
            schema.tables.extend(sub_schema.tables)
            schema.source_files.append(str(f))
        except (OSError, UnicodeDecodeError):
            pass

    # apply ALTER TABLE statements
    for f in files:
        try:
            sql = f.read_text()
            _apply_alters(schema, sql)
        except (OSError, UnicodeDecodeError):
            pass

    # deduplicate tables (later definitions override earlier)
    seen = {}
    for t in schema.tables:
        seen[t.name] = t
    schema.tables = list(seen.values())

    return schema


def detect_schema(root: str = ".") -> Schema:
    """auto-detect and parse database schema from project files."""
    root_path = Path(root)
    schema = Schema()

    # check common migration directories
    migration_dirs = [
        "migrations", "db/migrations", "alembic/versions",
        "prisma/migrations", "database/migrations",
    ]
    for mdir in migration_dirs:
        full = root_path / mdir
        if full.is_dir():
            sub = parse_migration_dir(str(full))
            schema.tables.extend(sub.tables)
            schema.source_files.extend(sub.source_files)

    # check for schema.sql
    for schema_file in ["schema.sql", "db/schema.sql", "database/schema.sql"]:
        f = root_path / schema_file
        if f.exists():
            sub = parse_sql(f.read_text())
            schema.tables.extend(sub.tables)
            schema.source_files.append(str(f))

    # check for SQLAlchemy/Django models
    for py_file in root_path.rglob("models.py"):
        models = parse_orm_models(str(py_file))
        schema.tables.extend(models)
        if models:
            schema.source_files.append(str(py_file))

    # deduplicate
    seen = {}
    for t in schema.tables:
        seen[t.name] = t
    schema.tables = list(seen.values())

    return schema


def _extract_balanced_parens(sql: str, start: int) -> str | None:
    """extract content between balanced parentheses starting at start position."""
    depth = 1
    i = start
    while i < len(sql) and depth > 0:
        if sql[i] == '(':
            depth += 1
        elif sql[i] == ')':
            depth -= 1
        i += 1
    if depth == 0:
        return sql[start:i - 1]
    return None


def _parse_columns(body: str) -> list[Column]:
    """parse column definitions from CREATE TABLE body."""
    columns = []
    # split on commas but not commas inside parentheses
    parts = _split_columns(body)
    for line in parts:
        line = line.strip()
        if not line:
            continue
        # skip constraints
        upper = line.upper()
        if any(upper.startswith(kw) for kw in ["PRIMARY KEY", "UNIQUE", "CHECK", "CONSTRAINT", "FOREIGN KEY"]):
            continue

        parts = line.split()
        if len(parts) < 2:
            continue

        name = parts[0].strip('"`')
        col_type = parts[1].strip('"`')

        nullable = "NOT NULL" not in upper
        pk = "PRIMARY KEY" in upper
        default = ""
        references = ""

        # extract DEFAULT
        if "DEFAULT" in upper:
            idx = upper.index("DEFAULT")
            rest = line[idx + 7:].strip()
            default = rest.split()[0] if rest else ""

        # extract REFERENCES
        ref_match = re.search(r'REFERENCES\s+["`]?(\w+)["`]?\s*\(["`]?(\w+)["`]?\)', line, re.IGNORECASE)
        if ref_match:
            references = f"{ref_match.group(1)}.{ref_match.group(2)}"

        columns.append(Column(
            name=name, type=col_type,
            nullable=nullable, primary_key=pk,
            default=default, references=references,
        ))
    return columns


def _apply_alters(schema: Schema, sql: str):
    """apply ALTER TABLE statements to schema."""
    for match in re.finditer(
        r'ALTER\s+TABLE\s+["`]?(\w+)["`]?\s+ADD\s+(?:COLUMN\s+)?["`]?(\w+)["`]?\s+(\w+)',
        sql, re.IGNORECASE,
    ):
        table_name, col_name, col_type = match.groups()
        table = schema.get_table(table_name)
        if table:
            table.columns.append(Column(name=col_name, type=col_type))


# ============================================================
# ORM MODEL PARSING
# ============================================================

def _split_columns(body: str) -> list[str]:
    """split column definitions, respecting parentheses."""
    parts = []
    depth = 0
    current = []
    for char in body:
        if char == '(':
            depth += 1
            current.append(char)
        elif char == ')':
            depth -= 1
            current.append(char)
        elif char == ',' and depth == 0:
            parts.append(''.join(current))
            current = []
        else:
            current.append(char)
    if current:
        parts.append(''.join(current))
    return parts


def parse_orm_models(filepath: str) -> list[Table]:
    """parse SQLAlchemy or Django models from a Python file."""
    path = Path(filepath)
    if not path.exists():
        return []

    try:
        source = path.read_text()
        tree = ast.parse(source)
    except (SyntaxError, OSError):
        return []

    tables = []
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        # check if it's a model class
        base_names = [_get_base_name(b) for b in node.bases]
        is_sqlalchemy = any(b in ("Base", "Model", "db.Model") for b in base_names)
        is_django = any("Model" in b for b in base_names)

        if not is_sqlalchemy and not is_django:
            continue

        table_name = _class_to_table_name(node.name)
        columns = []

        for item in ast.iter_child_nodes(node):
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        col = _parse_orm_column(target.id, item.value, source)
                        if col:
                            columns.append(col)

            # check for __tablename__
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "__tablename__":
                        if isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):
                            table_name = item.value.value

        if columns:
            tables.append(Table(name=table_name, columns=columns))

    return tables


def _get_base_name(node) -> str:
    """get string name from a base class node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_get_base_name(node.value)}.{node.attr}"
    return ""


def _class_to_table_name(class_name: str) -> str:
    """convert CamelCase to snake_case table name."""
    result = re.sub(r'([A-Z])', r'_\1', class_name).lower().lstrip('_')
    return result + "s" if not result.endswith("s") else result


def _parse_orm_column(name: str, value, source: str) -> Column | None:
    """parse an ORM column assignment."""
    # skip private/meta
    if name.startswith("_"):
        return None

    # get the source text for this assignment to detect Column() calls
    try:
        line = source.split("\n")[value.lineno - 1] if hasattr(value, 'lineno') else ""
    except (IndexError, AttributeError):
        line = ""

    # detect Column() or db.Column()
    if "Column(" in line or "Field(" in line:
        col_type = _extract_orm_type(line)
        nullable = "nullable=False" not in line
        pk = "primary_key=True" in line
        fk = ""
        fk_match = re.search(r'ForeignKey\(["\'](\w+\.\w+)["\']\)', line)
        if fk_match:
            fk = fk_match.group(1)
        return Column(
            name=name, type=col_type,
            nullable=nullable, primary_key=pk,
            references=fk,
        )

    return None


def _extract_orm_type(line: str) -> str:
    """extract the type from a Column() or Field() call."""
    # look for Column(Integer, ...) or Column(db.String(50), ...)
    match = re.search(r'(?:Column|Field)\(\s*(?:db\.)?(\w+)', line)
    if match:
        return match.group(1).lower()
    return "unknown"


# ============================================================
# QUERY ANALYSIS
# ============================================================

@dataclass
class QueryAnalysis:
    """analysis of a SQL query."""
    query_type: str  # SELECT, INSERT, UPDATE, DELETE
    tables: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    has_where: bool = False
    has_join: bool = False
    has_subquery: bool = False
    has_order_by: bool = False
    has_group_by: bool = False
    has_limit: bool = False
    warnings: list[str] = field(default_factory=list)


def analyze_query(sql: str) -> QueryAnalysis:
    """analyze a SQL query for potential issues."""
    upper = sql.upper().strip()

    # detect query type
    query_type = "UNKNOWN"
    for qt in ["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP"]:
        if upper.startswith(qt):
            query_type = qt
            break

    analysis = QueryAnalysis(query_type=query_type)

    # extract tables
    for match in re.finditer(r'(?:FROM|JOIN|INTO|UPDATE)\s+["`]?(\w+)["`]?', sql, re.IGNORECASE):
        table = match.group(1)
        if table.upper() not in ("SELECT", "WHERE", "SET", "VALUES"):
            analysis.tables.append(table)

    # detect features
    analysis.has_where = bool(re.search(r'\bWHERE\b', sql, re.IGNORECASE))
    analysis.has_join = bool(re.search(r'\bJOIN\b', sql, re.IGNORECASE))
    analysis.has_subquery = sql.count("(") > 0 and bool(re.search(r'\(\s*SELECT', sql, re.IGNORECASE))
    analysis.has_order_by = bool(re.search(r'\bORDER\s+BY\b', sql, re.IGNORECASE))
    analysis.has_group_by = bool(re.search(r'\bGROUP\s+BY\b', sql, re.IGNORECASE))
    analysis.has_limit = bool(re.search(r'\bLIMIT\b', sql, re.IGNORECASE))

    # warnings
    if query_type == "SELECT" and not analysis.has_where and not analysis.has_limit:
        analysis.warnings.append("SELECT without WHERE or LIMIT (full table scan)")
    if query_type == "DELETE" and not analysis.has_where:
        analysis.warnings.append("DELETE without WHERE (will delete all rows)")
    if query_type == "UPDATE" and not analysis.has_where:
        analysis.warnings.append("UPDATE without WHERE (will update all rows)")
    if "SELECT *" in sql.upper():
        analysis.warnings.append("SELECT * (consider specifying columns)")
    if analysis.has_subquery:
        analysis.warnings.append("Contains subquery (consider using JOIN for performance)")

    return analysis


def suggest_indexes(schema: Schema, queries: list[str]) -> list[dict]:
    """suggest indexes based on query patterns."""
    suggestions = []
    column_usage: dict[str, dict[str, int]] = {}  # table -> {column -> count}

    for query in queries:
        analysis = analyze_query(query)
        # extract WHERE columns
        for match in re.finditer(r'WHERE\s+.*?["`]?(\w+)["`]?\s*[=<>!]', query, re.IGNORECASE):
            col = match.group(1)
            for table in analysis.tables:
                t = schema.get_table(table)
                if t and col in t.column_names():
                    column_usage.setdefault(table, {}).setdefault(col, 0)
                    column_usage[table][col] += 1

        # extract ORDER BY columns
        for match in re.finditer(r'ORDER\s+BY\s+["`]?(\w+)["`]?', query, re.IGNORECASE):
            col = match.group(1)
            for table in analysis.tables:
                t = schema.get_table(table)
                if t and col in t.column_names():
                    column_usage.setdefault(table, {}).setdefault(col, 0)
                    column_usage[table][col] += 1

    for table, cols in column_usage.items():
        for col, count in cols.items():
            if count >= 2:  # used in multiple queries
                suggestions.append({
                    "table": table,
                    "column": col,
                    "usage_count": count,
                    "sql": f"CREATE INDEX idx_{table}_{col} ON {table}({col})",
                })

    return sorted(suggestions, key=lambda s: -s["usage_count"])


# ============================================================
# CODE GENERATION
# ============================================================

def generate_model(table: Table, style: str = "dataclass") -> str:
    """generate a Python model from a table definition."""
    class_name = _table_to_class_name(table.name)

    if style == "dataclass":
        lines = ["from dataclasses import dataclass", "", "", "@dataclass"]
        lines.append(f"class {class_name}:")
        lines.append(f'    """model for {table.name} table."""')
        for col in table.columns:
            py_type = _sql_to_python_type(col.type)
            default = ""
            if col.nullable and not col.primary_key:
                py_type = f"{py_type} | None"
                default = " = None"
            elif col.default:
                default = f" = {col.default}"
            lines.append(f"    {col.name}: {py_type}{default}")
        return "\n".join(lines) + "\n"

    elif style == "sqlalchemy":
        lines = [
            "from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey",
            "from sqlalchemy.orm import DeclarativeBase",
            "", "",
            "class Base(DeclarativeBase):",
            "    pass",
            "", "",
            f"class {class_name}(Base):",
            f'    __tablename__ = "{table.name}"',
            "",
        ]
        for col in table.columns:
            sa_type = _sql_to_sa_type(col.type)
            extras = []
            if col.primary_key:
                extras.append("primary_key=True")
            if not col.nullable:
                extras.append("nullable=False")
            if col.references:
                extras.append(f'ForeignKey("{col.references}")')
            extras_str = ", ".join([sa_type] + extras)
            lines.append(f"    {col.name} = Column({extras_str})")
        return "\n".join(lines) + "\n"

    return ""


def _table_to_class_name(table_name: str) -> str:
    """convert snake_case table name to CamelCase class name."""
    # remove trailing 's' for plurals
    name = table_name.rstrip("s") if table_name.endswith("s") and not table_name.endswith("ss") else table_name
    return "".join(word.capitalize() for word in name.split("_"))


def _sql_to_python_type(sql_type: str) -> str:
    """map SQL types to Python types."""
    mapping = {
        "integer": "int", "int": "int", "bigint": "int", "smallint": "int",
        "serial": "int", "bigserial": "int",
        "varchar": "str", "text": "str", "char": "str", "string": "str",
        "boolean": "bool", "bool": "bool",
        "float": "float", "double": "float", "real": "float", "numeric": "float",
        "decimal": "float",
        "timestamp": "str", "datetime": "str", "date": "str", "time": "str",
        "json": "dict", "jsonb": "dict",
        "uuid": "str",
    }
    return mapping.get(sql_type.lower().split("(")[0], "str")


def _sql_to_sa_type(sql_type: str) -> str:
    """map SQL types to SQLAlchemy types."""
    mapping = {
        "integer": "Integer", "int": "Integer", "bigint": "Integer",
        "serial": "Integer", "bigserial": "Integer",
        "varchar": "String", "text": "String", "char": "String", "string": "String",
        "boolean": "Boolean", "bool": "Boolean",
        "float": "Float", "double": "Float", "real": "Float",
        "timestamp": "DateTime", "datetime": "DateTime",
    }
    return mapping.get(sql_type.lower().split("(")[0], "String")
