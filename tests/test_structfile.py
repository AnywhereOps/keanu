"""Tests for structfile.py - structured config file parsing."""

from keanu.tools.structfile import (
    parse_toml, parse_ini, parse_env, parse_yaml_simple,
    write_toml, write_ini, write_env,
    detect_format, parse_file, merge_configs,
)


class TestParseToml:
    def test_strings(self):
        d = parse_toml('name = "keanu"\npath = \'single\'')
        assert d["name"] == "keanu"
        assert d["path"] == "single"

    def test_integers_and_floats(self):
        d = parse_toml("port = 8080\npi = 3.14")
        assert d["port"] == 8080
        assert d["pi"] == 3.14

    def test_booleans(self):
        d = parse_toml("debug = true\nverbose = false")
        assert d["debug"] is True
        assert d["verbose"] is False

    def test_arrays(self):
        d = parse_toml('tags = ["a", "b", "c"]')
        assert d["tags"] == ["a", "b", "c"]

    def test_empty_array(self):
        d = parse_toml("items = []")
        assert d["items"] == []

    def test_tables(self):
        d = parse_toml("[server]\nhost = \"localhost\"\nport = 9090")
        assert d["server"]["host"] == "localhost"
        assert d["server"]["port"] == 9090

    def test_nested_tables(self):
        d = parse_toml("[tool.poetry]\nname = \"keanu\"")
        assert d["tool"]["poetry"]["name"] == "keanu"

    def test_dotted_keys(self):
        d = parse_toml('tool.name = "keanu"')
        assert d["tool"]["name"] == "keanu"

    def test_inline_tables(self):
        d = parse_toml('server = {host = "localhost", port = 8080}')
        assert d["server"]["host"] == "localhost"
        assert d["server"]["port"] == 8080

    def test_array_of_tables(self):
        toml = '[[fruits]]\nname = "apple"\n\n[[fruits]]\nname = "banana"'
        d = parse_toml(toml)
        assert len(d["fruits"]) == 2
        assert d["fruits"][0]["name"] == "apple"
        assert d["fruits"][1]["name"] == "banana"

    def test_comments_ignored(self):
        d = parse_toml('# comment\nname = "val" # inline')
        assert d["name"] == "val"

    def test_pyproject_style(self):
        toml = """
[project]
name = "keanu"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["chromadb", "rich", "requests"]

[tool.pytest.ini_options]
testpaths = ["tests"]
"""
        d = parse_toml(toml)
        assert d["project"]["name"] == "keanu"
        assert d["project"]["dependencies"] == ["chromadb", "rich", "requests"]
        assert d["tool"]["pytest"]["ini_options"]["testpaths"] == ["tests"]


class TestParseIni:
    def test_sections(self):
        d = parse_ini("[db]\nhost = localhost\nport = 5432")
        assert d["db"]["host"] == "localhost"
        assert d["db"]["port"] == 5432

    def test_key_equals_value(self):
        d = parse_ini("[s]\nkey = value")
        assert d["s"]["key"] == "value"

    def test_key_colon_value(self):
        d = parse_ini("[s]\nkey: value")
        assert d["s"]["key"] == "value"

    def test_hash_comments(self):
        d = parse_ini("# comment\n[s]\nk = v # inline")
        assert d["s"]["k"] == "v"

    def test_semicolon_comments(self):
        d = parse_ini("; comment\n[s]\nk = v")
        assert d["s"]["k"] == "v"

    def test_boolean_coercion(self):
        d = parse_ini("[s]\nenabled = true\nverbose = false")
        assert d["s"]["enabled"] is True
        assert d["s"]["verbose"] is False

    def test_top_level_keys(self):
        d = parse_ini("global = yes\n[s]\nlocal = no")
        assert d["global"] == "yes"
        assert d["s"]["local"] == "no"


class TestParseEnv:
    def test_basic(self):
        d = parse_env("API_KEY=secret123\nDEBUG=true")
        assert d["API_KEY"] == "secret123"
        assert d["DEBUG"] == "true"

    def test_quoted_values(self):
        d = parse_env('DB_URL="postgres://localhost/db"\nNAME=\'single\'')
        assert d["DB_URL"] == "postgres://localhost/db"
        assert d["NAME"] == "single"

    def test_export_prefix(self):
        d = parse_env("export TOKEN=abc123")
        assert d["TOKEN"] == "abc123"

    def test_comments_and_blanks(self):
        d = parse_env("# comment\n\nKEY=val\n  \n# another")
        assert d == {"KEY": "val"}

    def test_value_with_equals(self):
        d = parse_env('CONN="host=localhost port=5432"')
        assert d["CONN"] == "host=localhost port=5432"


class TestParseYamlSimple:
    def test_flat_key_value(self):
        d = parse_yaml_simple("name: keanu\nversion: 1")
        assert d["name"] == "keanu"
        assert d["version"] == 1

    def test_boolean_values(self):
        d = parse_yaml_simple("debug: true\nverbose: false")
        assert d["debug"] is True
        assert d["verbose"] is False

    def test_lists(self):
        d = parse_yaml_simple("items:\n  - alpha\n  - beta\n  - gamma")
        assert d["items"] == ["alpha", "beta", "gamma"]

    def test_nested_block(self):
        d = parse_yaml_simple("server:\n  host: localhost\n  port: 8080")
        assert d["server"]["host"] == "localhost"
        assert d["server"]["port"] == 8080

    def test_comments_ignored(self):
        d = parse_yaml_simple("# comment\nkey: val # inline")
        assert d["key"] == "val"

    def test_quoted_strings(self):
        d = parse_yaml_simple('name: "hello world"')
        assert d["name"] == "hello world"

    def test_null_values(self):
        d = parse_yaml_simple("empty: null\ntilde: ~")
        assert d["empty"] is None
        assert d["tilde"] is None


class TestWriteToml:
    def test_roundtrip(self):
        original = {"name": "keanu", "version": 1, "debug": True}
        text = write_toml(original)
        parsed = parse_toml(text)
        assert parsed == original

    def test_tables(self):
        data = {"project": {"name": "keanu", "version": 1}}
        text = write_toml(data)
        assert "[project]" in text
        parsed = parse_toml(text)
        assert parsed["project"]["name"] == "keanu"

    def test_arrays(self):
        data = {"tags": ["a", "b"]}
        text = write_toml(data)
        parsed = parse_toml(text)
        assert parsed["tags"] == ["a", "b"]


class TestWriteIni:
    def test_roundtrip(self):
        original = {"section": {"host": "localhost", "port": 5432}}
        text = write_ini(original)
        parsed = parse_ini(text)
        assert parsed["section"]["host"] == "localhost"
        assert parsed["section"]["port"] == 5432

    def test_section_header(self):
        text = write_ini({"db": {"host": "localhost"}})
        assert "[db]" in text


class TestWriteEnv:
    def test_roundtrip(self):
        original = {"API_KEY": "secret", "DEBUG": "true"}
        text = write_env(original)
        parsed = parse_env(text)
        assert parsed == original

    def test_quoted_spaces(self):
        text = write_env({"MSG": "hello world"})
        assert '"hello world"' in text


class TestDetectFormat:
    def test_toml(self):
        assert detect_format("pyproject.toml") == "toml"

    def test_ini(self):
        assert detect_format("setup.ini") == "ini"

    def test_cfg(self):
        assert detect_format("setup.cfg") == "ini"

    def test_env(self):
        assert detect_format(".env") == "env"

    def test_yaml(self):
        assert detect_format("config.yaml") == "yaml"

    def test_yml(self):
        assert detect_format("docker-compose.yml") == "yaml"

    def test_unknown(self):
        assert detect_format("readme.md") == "unknown"


class TestParseFile:
    def test_toml_file(self, tmp_path):
        f = tmp_path / "test.toml"
        f.write_text('name = "keanu"\nport = 8080')
        d = parse_file(str(f))
        assert d["name"] == "keanu"
        assert d["port"] == 8080

    def test_ini_file(self, tmp_path):
        f = tmp_path / "test.ini"
        f.write_text("[db]\nhost = localhost")
        d = parse_file(str(f))
        assert d["db"]["host"] == "localhost"

    def test_env_file(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("KEY=val")
        d = parse_file(str(f))
        assert d["KEY"] == "val"

    def test_yaml_file(self, tmp_path):
        f = tmp_path / "config.yml"
        f.write_text("name: keanu\nversion: 2")
        d = parse_file(str(f))
        assert d["name"] == "keanu"
        assert d["version"] == 2

    def test_unknown_raises(self, tmp_path):
        f = tmp_path / "data.bin"
        f.write_text("stuff")
        try:
            parse_file(str(f))
            assert False, "should have raised"
        except ValueError:
            pass


class TestMergeConfigs:
    def test_flat_merge(self):
        base = {"a": 1, "b": 2}
        overlay = {"b": 3, "c": 4}
        merged = merge_configs(base, overlay)
        assert merged == {"a": 1, "b": 3, "c": 4}

    def test_deep_merge(self):
        base = {"db": {"host": "localhost", "port": 5432}}
        overlay = {"db": {"port": 3306, "name": "mydb"}}
        merged = merge_configs(base, overlay)
        assert merged["db"]["host"] == "localhost"
        assert merged["db"]["port"] == 3306
        assert merged["db"]["name"] == "mydb"

    def test_overlay_wins(self):
        base = {"key": "old", "nested": {"a": 1}}
        overlay = {"key": "new", "nested": {"a": 2}}
        merged = merge_configs(base, overlay)
        assert merged["key"] == "new"
        assert merged["nested"]["a"] == 2

    def test_base_unchanged(self):
        base = {"a": 1}
        overlay = {"a": 2}
        merge_configs(base, overlay)
        assert base["a"] == 1
