"""tests for database awareness."""

from keanu.data.database import (
    parse_sql, parse_migration_dir, detect_schema, parse_orm_models,
    analyze_query, suggest_indexes, generate_model,
    Schema, Table, Column, QueryAnalysis,
    _class_to_table_name, _table_to_class_name,
)


class TestParseSql:

    def test_simple_create_table(self):
        sql = """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email TEXT
        )
        """
        schema = parse_sql(sql)
        assert len(schema.tables) == 1
        t = schema.tables[0]
        assert t.name == "users"
        assert len(t.columns) == 3
        assert t.columns[0].name == "id"
        assert t.columns[0].primary_key

    def test_foreign_key(self):
        sql = """
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            title TEXT NOT NULL
        )
        """
        schema = parse_sql(sql)
        t = schema.tables[0]
        fk = [c for c in t.columns if c.references]
        assert len(fk) == 1
        assert fk[0].references == "users.id"

    def test_multiple_tables(self):
        sql = """
        CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE posts (id INTEGER PRIMARY KEY, title TEXT);
        """
        schema = parse_sql(sql)
        assert len(schema.tables) == 2

    def test_if_not_exists(self):
        sql = "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY)"
        schema = parse_sql(sql)
        assert schema.tables[0].name == "users"

    def test_default_value(self):
        sql = "CREATE TABLE t (active BOOLEAN DEFAULT true)"
        schema = parse_sql(sql)
        assert schema.tables[0].columns[0].default == "true"


class TestParseMigrationDir:

    def test_parses_directory(self, tmp_path):
        (tmp_path / "001_create_users.sql").write_text(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);"
        )
        (tmp_path / "002_create_posts.sql").write_text(
            "CREATE TABLE posts (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id));"
        )
        schema = parse_migration_dir(str(tmp_path))
        assert len(schema.tables) == 2
        assert len(schema.source_files) == 2

    def test_empty_dir(self, tmp_path):
        schema = parse_migration_dir(str(tmp_path))
        assert schema.tables == []

    def test_nonexistent_dir(self):
        schema = parse_migration_dir("/nonexistent")
        assert schema.tables == []


class TestParseOrmModels:

    def test_sqlalchemy_model(self, tmp_path):
        f = tmp_path / "models.py"
        f.write_text('''
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String)
''')
        tables = parse_orm_models(str(f))
        assert len(tables) == 1
        assert tables[0].name == "users"
        assert len(tables[0].columns) == 3

    def test_nonexistent_file(self):
        tables = parse_orm_models("/nonexistent.py")
        assert tables == []


class TestSchema:

    def test_table_names(self):
        s = Schema(tables=[Table(name="users"), Table(name="posts")])
        assert s.table_names() == ["users", "posts"]

    def test_get_table(self):
        s = Schema(tables=[Table(name="users")])
        assert s.get_table("users").name == "users"
        assert s.get_table("nope") is None

    def test_relationships(self):
        t = Table(name="posts", columns=[
            Column(name="user_id", type="int", references="users.id"),
        ])
        s = Schema(tables=[t])
        rels = s.relationships()
        assert len(rels) == 1
        assert rels[0]["from_table"] == "posts"
        assert rels[0]["to_table"] == "users"


class TestAnalyzeQuery:

    def test_select(self):
        a = analyze_query("SELECT * FROM users WHERE id = 1")
        assert a.query_type == "SELECT"
        assert "users" in a.tables
        assert a.has_where

    def test_select_star_warning(self):
        a = analyze_query("SELECT * FROM users")
        assert any("SELECT *" in w for w in a.warnings)

    def test_no_where_warning(self):
        a = analyze_query("SELECT id FROM users")
        assert any("without WHERE" in w for w in a.warnings)

    def test_delete_no_where(self):
        a = analyze_query("DELETE FROM users")
        assert any("DELETE without WHERE" in w for w in a.warnings)

    def test_update_no_where(self):
        a = analyze_query("UPDATE users SET name = 'x'")
        assert any("UPDATE without WHERE" in w for w in a.warnings)

    def test_join(self):
        a = analyze_query("SELECT u.name FROM users u JOIN posts p ON u.id = p.user_id")
        assert a.has_join
        assert "users" in a.tables

    def test_subquery(self):
        a = analyze_query("SELECT * FROM users WHERE id IN (SELECT user_id FROM posts)")
        assert a.has_subquery

    def test_order_by(self):
        a = analyze_query("SELECT * FROM users ORDER BY name LIMIT 10")
        assert a.has_order_by
        assert a.has_limit
        # has LIMIT so no "full table scan" warning
        assert not any("full table scan" in w for w in a.warnings)


class TestSuggestIndexes:

    def test_suggests_from_where(self):
        schema = Schema(tables=[
            Table(name="users", columns=[
                Column(name="id", type="int"), Column(name="email", type="text"),
            ]),
        ])
        queries = [
            "SELECT * FROM users WHERE email = 'x'",
            "SELECT * FROM users WHERE email = 'y'",
        ]
        suggestions = suggest_indexes(schema, queries)
        assert len(suggestions) >= 1
        assert suggestions[0]["column"] == "email"


class TestGenerateModel:

    def test_dataclass(self):
        table = Table(name="users", columns=[
            Column(name="id", type="integer", primary_key=True),
            Column(name="name", type="varchar", nullable=False),
            Column(name="bio", type="text"),
        ])
        code = generate_model(table, style="dataclass")
        assert "class User:" in code
        assert "id: int" in code
        assert "name: str" in code
        assert "bio: str | None = None" in code

    def test_sqlalchemy(self):
        table = Table(name="users", columns=[
            Column(name="id", type="integer", primary_key=True),
            Column(name="name", type="varchar", nullable=False),
        ])
        code = generate_model(table, style="sqlalchemy")
        assert "class User(Base):" in code
        assert "primary_key=True" in code
        assert "nullable=False" in code


class TestNameConversions:

    def test_class_to_table(self):
        assert _class_to_table_name("User") == "users"
        assert _class_to_table_name("BlogPost") == "blog_posts"

    def test_table_to_class(self):
        assert _table_to_class_name("users") == "User"
        assert _table_to_class_name("blog_posts") == "BlogPost"
