"""Tests for the template engine: render, validate, save/load, built-ins."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from keanu.gen.templates import (
    Template, TemplateVar, render, validate_context,
    save_template, load_template, delete_template, list_templates,
    get_template, render_to_file, from_file,
    BUILTIN_TEMPLATES, TEMPLATES_DIR,
)


# ============================================================
# RENDER
# ============================================================

class TestRender:

    def test_basic_substitution(self):
        t = Template(name="t", content="hello {{name}}")
        assert render(t, {"name": "world"}) == "hello world"

    def test_multiple_vars(self):
        t = Template(name="t", content="{{a}} and {{b}}")
        assert render(t, {"a": "fire", "b": "ash"}) == "fire and ash"

    def test_inline_default(self):
        t = Template(name="t", content="{{name|stranger}}")
        assert render(t, {}) == "stranger"

    def test_inline_default_overridden(self):
        t = Template(name="t", content="{{name|stranger}}")
        assert render(t, {"name": "drew"}) == "drew"

    def test_templatevar_default(self):
        t = Template(name="t", content="{{x}}",
                     variables=[TemplateVar("x", default="fallback")])
        assert render(t, {}) == "fallback"

    def test_no_match_preserved(self):
        t = Template(name="t", content="{{unknown}}")
        assert render(t, {}) == "{{unknown}}"

    def test_empty_inline_default(self):
        t = Template(name="t", content="({{opt|}})")
        assert render(t, {}) == "()"


# ============================================================
# VALIDATE
# ============================================================

class TestValidate:

    def test_all_present(self):
        t = Template(name="t", content="",
                     variables=[TemplateVar("a", required=True)])
        ok, missing = validate_context(t, {"a": "val"})
        assert ok
        assert missing == []

    def test_missing_required(self):
        t = Template(name="t", content="",
                     variables=[TemplateVar("a", required=True),
                                TemplateVar("b", required=True)])
        ok, missing = validate_context(t, {"a": "val"})
        assert not ok
        assert missing == ["b"]

    def test_optional_not_required(self):
        t = Template(name="t", content="",
                     variables=[TemplateVar("a", required=False)])
        ok, missing = validate_context(t, {})
        assert ok

    def test_required_with_default_ok(self):
        t = Template(name="t", content="",
                     variables=[TemplateVar("a", required=True, default="x")])
        ok, missing = validate_context(t, {})
        assert ok


# ============================================================
# SAVE / LOAD / DELETE / LIST
# ============================================================

class TestPersistence:

    @pytest.fixture(autouse=True)
    def use_tmp(self, tmp_path):
        self.tdir = tmp_path / "templates"
        self.tdir.mkdir()
        with patch("keanu.gen.templates.TEMPLATES_DIR", self.tdir):
            yield

    def test_save_and_load(self):
        t = Template(name="greet", content="hi {{who}}",
                     variables=[TemplateVar("who", "person")])
        save_template(t)
        loaded = load_template("greet")
        assert loaded.name == "greet"
        assert loaded.content == "hi {{who}}"
        assert len(loaded.variables) == 1
        assert loaded.variables[0].name == "who"

    def test_load_missing_raises(self):
        with pytest.raises(FileNotFoundError):
            load_template("nonexistent")

    def test_delete_existing(self):
        t = Template(name="tmp", content="x")
        save_template(t)
        assert delete_template("tmp")
        with pytest.raises(FileNotFoundError):
            load_template("tmp")

    def test_delete_missing(self):
        assert not delete_template("nope")

    def test_list_all(self):
        save_template(Template(name="a", content="1", category="code"))
        save_template(Template(name="b", content="2", category="test"))
        result = list_templates()
        assert len(result) == 2

    def test_list_filtered_category(self):
        save_template(Template(name="a", content="1", category="code"))
        save_template(Template(name="b", content="2", category="test"))
        result = list_templates(category="code")
        assert len(result) == 1
        assert result[0].name == "a"

    def test_list_filtered_language(self):
        save_template(Template(name="a", content="1", language="python"))
        save_template(Template(name="b", content="2", language="rust"))
        result = list_templates(language="rust")
        assert len(result) == 1
        assert result[0].name == "b"


# ============================================================
# BUILT-INS
# ============================================================

class TestBuiltins:

    def test_all_registered(self):
        expected = {"python_function", "python_class", "python_test",
                    "python_dataclass", "fastapi_endpoint", "cli_command"}
        assert expected.issubset(set(BUILTIN_TEMPLATES.keys()))

    def test_render_python_function(self):
        t = BUILTIN_TEMPLATES["python_function"]
        out = render(t, {"name": "greet", "params": "name: str",
                         "body": 'return f"hi {name}"'})
        assert "def greet(name: str):" in out
        assert 'return f"hi {name}"' in out

    def test_render_python_class(self):
        t = BUILTIN_TEMPLATES["python_class"]
        out = render(t, {"name": "Dog", "init_params": ", breed: str",
                         "init_body": "self.breed = breed"})
        assert "class Dog:" in out
        assert "self.breed = breed" in out

    def test_render_with_defaults(self):
        t = BUILTIN_TEMPLATES["python_function"]
        out = render(t, {"name": "noop"})
        assert "def noop(" in out
        assert "pass" in out


# ============================================================
# GET_TEMPLATE (precedence)
# ============================================================

class TestGetTemplate:

    @pytest.fixture(autouse=True)
    def use_tmp(self, tmp_path):
        self.tdir = tmp_path / "templates"
        self.tdir.mkdir()
        with patch("keanu.gen.templates.TEMPLATES_DIR", self.tdir):
            yield

    def test_returns_builtin(self):
        t = get_template("python_function")
        assert t.name == "python_function"

    def test_user_overrides_builtin(self):
        user_t = Template(name="python_function", content="custom {{name}}")
        save_template(user_t)
        t = get_template("python_function")
        assert t.content == "custom {{name}}"

    def test_missing_raises(self):
        with pytest.raises(FileNotFoundError):
            get_template("does_not_exist")


# ============================================================
# RENDER_TO_FILE
# ============================================================

class TestRenderToFile:

    @pytest.fixture(autouse=True)
    def use_tmp(self, tmp_path):
        self.tdir = tmp_path / "templates"
        self.tdir.mkdir()
        self.out_dir = tmp_path / "output"
        with patch("keanu.gen.templates.TEMPLATES_DIR", self.tdir):
            yield

    def test_writes_file(self):
        out = self.out_dir / "greet.py"
        content = render_to_file("python_function", {"name": "hello"}, str(out))
        assert out.exists()
        assert "def hello(" in content
        assert out.read_text() == content


# ============================================================
# FROM_FILE
# ============================================================

class TestFromFile:

    def test_parse_header(self, tmp_path):
        f = tmp_path / "my.tmpl"
        f.write_text("# template: name=greeter language=python category=code vars=name,msg\nhello {{name}}: {{msg}}")
        t = from_file(str(f))
        assert t.name == "greeter"
        assert t.language == "python"
        assert t.category == "code"
        assert len(t.variables) == 2
        assert t.variables[0].name == "name"
        assert "hello {{name}}" in t.content

    def test_missing_header_raises(self, tmp_path):
        f = tmp_path / "bad.tmpl"
        f.write_text("no header here")
        with pytest.raises(ValueError):
            from_file(str(f))

    def test_no_vars(self, tmp_path):
        f = tmp_path / "bare.tmpl"
        f.write_text("# template: name=bare\nstatic content")
        t = from_file(str(f))
        assert t.name == "bare"
        assert t.variables == []
