"""tests for database migration helpers."""

from keanu.data.migrate import (
    generate_create_table, generate_add_column, generate_drop_column,
    generate_create_index, generate_rename_column,
    diff_schemas, diff_to_sql, SchemaDiff,
    create_migration_file, list_migrations, parse_migration_file,
    detect_migration_system, migration_status,
    Migration, MigrationPlan,
)


class TestSQLGeneration:

    def test_create_table(self):
        sql = generate_create_table("users", {
            "id": "INTEGER PRIMARY KEY",
            "name": "TEXT NOT NULL",
            "email": "TEXT UNIQUE",
        })
        assert "CREATE TABLE users" in sql
        assert "id INTEGER PRIMARY KEY" in sql
        assert "name TEXT NOT NULL" in sql

    def test_add_column(self):
        sql = generate_add_column("users", "age", "INTEGER DEFAULT 0")
        assert "ALTER TABLE users ADD COLUMN age INTEGER DEFAULT 0" in sql

    def test_drop_column(self):
        sql = generate_drop_column("users", "age")
        assert "ALTER TABLE users DROP COLUMN age" in sql

    def test_create_index(self):
        sql = generate_create_index("users", ["email"])
        assert "CREATE INDEX idx_users_email ON users (email)" in sql

    def test_create_unique_index(self):
        sql = generate_create_index("users", ["email"], unique=True)
        assert "UNIQUE INDEX" in sql

    def test_create_composite_index(self):
        sql = generate_create_index("orders", ["user_id", "created_at"])
        assert "user_id, created_at" in sql

    def test_rename_column(self):
        sql = generate_rename_column("users", "name", "full_name")
        assert "RENAME COLUMN name TO full_name" in sql


class TestSchemaDiff:

    def test_added_table(self):
        old = {"users": {"id": "INT"}}
        new = {"users": {"id": "INT"}, "posts": {"id": "INT"}}
        diff = diff_schemas(old, new)
        assert "posts" in diff.added_tables
        assert diff.has_changes

    def test_dropped_table(self):
        old = {"users": {"id": "INT"}, "temp": {"id": "INT"}}
        new = {"users": {"id": "INT"}}
        diff = diff_schemas(old, new)
        assert "temp" in diff.dropped_tables

    def test_added_column(self):
        old = {"users": {"id": "INT"}}
        new = {"users": {"id": "INT", "name": "TEXT"}}
        diff = diff_schemas(old, new)
        assert len(diff.added_columns) == 1
        assert diff.added_columns[0] == ("users", "name", "TEXT")

    def test_dropped_column(self):
        old = {"users": {"id": "INT", "temp": "TEXT"}}
        new = {"users": {"id": "INT"}}
        diff = diff_schemas(old, new)
        assert len(diff.dropped_columns) == 1
        assert diff.dropped_columns[0] == ("users", "temp")

    def test_modified_column(self):
        old = {"users": {"name": "VARCHAR(50)"}}
        new = {"users": {"name": "VARCHAR(100)"}}
        diff = diff_schemas(old, new)
        assert len(diff.modified_columns) == 1
        assert diff.modified_columns[0] == ("users", "name", "VARCHAR(50)", "VARCHAR(100)")

    def test_no_changes(self):
        tables = {"users": {"id": "INT", "name": "TEXT"}}
        diff = diff_schemas(tables, tables)
        assert not diff.has_changes


class TestDiffToSql:

    def test_generates_sql(self):
        diff = SchemaDiff(
            added_columns=[("users", "email", "TEXT NOT NULL")],
            dropped_columns=[("users", "temp")],
        )
        sql = diff_to_sql(diff)
        assert "ADD COLUMN email" in sql
        assert "DROP COLUMN temp" in sql

    def test_empty_diff(self):
        diff = SchemaDiff()
        sql = diff_to_sql(diff)
        assert sql == ""


class TestMigrationFiles:

    def test_create_migration(self, tmp_path):
        mig_dir = str(tmp_path / "migrations")
        path = create_migration_file(
            "add users table",
            "CREATE TABLE users (id INT);",
            "DROP TABLE users;",
            migrations_dir=mig_dir,
        )
        assert "0001_add_users_table.sql" in path
        content = open(path).read()
        assert "CREATE TABLE users" in content
        assert "DROP TABLE users" in content

    def test_sequential_numbering(self, tmp_path):
        mig_dir = str(tmp_path / "migrations")
        create_migration_file("first", "SELECT 1;", migrations_dir=mig_dir)
        path = create_migration_file("second", "SELECT 2;", migrations_dir=mig_dir)
        assert "0002_second" in path

    def test_list_migrations(self, tmp_path):
        mig_dir = str(tmp_path / "migrations")
        create_migration_file("init", "CREATE TABLE x (id INT);", migrations_dir=mig_dir)
        create_migration_file("add col", "ALTER TABLE x ADD COLUMN y INT;", migrations_dir=mig_dir)
        migs = list_migrations(mig_dir)
        assert len(migs) == 2
        assert migs[0]["file"].startswith("0001_")

    def test_list_empty(self, tmp_path):
        assert list_migrations(str(tmp_path / "nope")) == []

    def test_parse_migration(self, tmp_path):
        mig_dir = str(tmp_path / "migrations")
        path = create_migration_file(
            "test",
            "CREATE TABLE x (id INT);",
            "DROP TABLE x;",
            migrations_dir=mig_dir,
        )
        mig = parse_migration_file(path)
        assert "CREATE TABLE x" in mig.sql_up
        assert "DROP TABLE x" in mig.sql_down


class TestMigration:

    def test_defaults(self):
        m = Migration(id="001", name="init", sql_up="CREATE TABLE x;")
        assert m.created_at > 0
        assert not m.applied

    def test_plan(self):
        plan = MigrationPlan(steps=[
            Migration(id="1", name="a", sql_up="CREATE TABLE a;"),
            Migration(id="2", name="b", sql_up="CREATE TABLE b;"),
        ])
        assert "CREATE TABLE a" in plan.sql
        assert "CREATE TABLE b" in plan.sql


class TestDetectSystem:

    def test_alembic(self, tmp_path):
        (tmp_path / "alembic.ini").write_text("[alembic]\n")
        assert detect_migration_system(str(tmp_path)) == "alembic"

    def test_django(self, tmp_path):
        mig = tmp_path / "migrations"
        mig.mkdir()
        (mig / "0001_initial.py").write_text("# migration\n")
        assert detect_migration_system(str(tmp_path)) == "django"

    def test_raw_sql(self, tmp_path):
        mig = tmp_path / "migrations"
        mig.mkdir()
        (mig / "001_init.sql").write_text("CREATE TABLE x;\n")
        assert detect_migration_system(str(tmp_path)) == "raw_sql"

    def test_prisma(self, tmp_path):
        (tmp_path / "prisma").mkdir()
        assert detect_migration_system(str(tmp_path)) == "prisma"

    def test_none(self, tmp_path):
        assert detect_migration_system(str(tmp_path)) == "none"


class TestMigrationStatus:

    def test_no_system(self, tmp_path):
        status = migration_status(str(tmp_path))
        assert status["system"] == "none"
        assert status["migrations"] == 0

    def test_raw_sql_count(self, tmp_path):
        mig = tmp_path / "migrations"
        mig.mkdir()
        (mig / "001.sql").write_text("CREATE TABLE a;\n")
        (mig / "002.sql").write_text("CREATE TABLE b;\n")
        status = migration_status(str(tmp_path))
        assert status["system"] == "raw_sql"
        assert status["migrations"] == 2
