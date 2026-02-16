"""tests for multi-language code analysis."""

from keanu.analysis.polyglot import (
    detect_language, list_symbols, find_definition, find_references,
    find_imports, project_languages, Symbol, Reference,
)


class TestDetectLanguage:

    def test_javascript(self):
        assert detect_language("app.js") == "javascript"
        assert detect_language("component.jsx") == "javascript"

    def test_typescript(self):
        assert detect_language("app.ts") == "typescript"
        assert detect_language("component.tsx") == "typescript"

    def test_go(self):
        assert detect_language("main.go") == "go"

    def test_rust(self):
        assert detect_language("lib.rs") == "rust"

    def test_ruby(self):
        assert detect_language("app.rb") == "ruby"

    def test_java(self):
        assert detect_language("Main.java") == "java"

    def test_c(self):
        assert detect_language("main.c") == "c"
        assert detect_language("main.cpp") == "cpp"
        assert detect_language("header.h") == "c"

    def test_unknown(self):
        assert detect_language("readme.md") == ""
        assert detect_language("data.json") == ""


class TestListSymbolsJS:

    def test_function(self, tmp_path):
        f = tmp_path / "app.js"
        f.write_text("function hello() {\n  return 'hi';\n}\n")
        symbols = list_symbols(str(f))
        assert len(symbols) >= 1
        assert symbols[0].name == "hello"
        assert symbols[0].kind == "function"

    def test_class(self, tmp_path):
        f = tmp_path / "app.js"
        f.write_text("export class MyComponent {\n  render() {}\n}\n")
        symbols = list_symbols(str(f))
        names = [s.name for s in symbols]
        assert "MyComponent" in names

    def test_arrow_function(self, tmp_path):
        f = tmp_path / "app.js"
        f.write_text("const greet = (name) => {\n  return `hi ${name}`;\n};\n")
        symbols = list_symbols(str(f))
        names = [s.name for s in symbols]
        assert "greet" in names

    def test_export_detection(self, tmp_path):
        f = tmp_path / "app.js"
        f.write_text("export function api() {}\nfunction internal() {}\n")
        symbols = list_symbols(str(f))
        exported = [s for s in symbols if s.exported]
        assert len(exported) == 1
        assert exported[0].name == "api"


class TestListSymbolsTS:

    def test_interface(self, tmp_path):
        f = tmp_path / "types.ts"
        f.write_text("export interface User {\n  name: string;\n}\n")
        symbols = list_symbols(str(f))
        assert any(s.name == "User" and s.kind == "interface" for s in symbols)

    def test_type_alias(self, tmp_path):
        f = tmp_path / "types.ts"
        f.write_text("export type ID = string | number;\n")
        symbols = list_symbols(str(f))
        assert any(s.name == "ID" and s.kind == "type" for s in symbols)

    def test_enum(self, tmp_path):
        f = tmp_path / "types.ts"
        f.write_text("export enum Color { Red, Green, Blue }\n")
        symbols = list_symbols(str(f))
        assert any(s.name == "Color" and s.kind == "enum" for s in symbols)


class TestListSymbolsGo:

    def test_function(self, tmp_path):
        f = tmp_path / "main.go"
        f.write_text("func main() {\n\tfmt.Println(\"hello\")\n}\n")
        symbols = list_symbols(str(f))
        assert any(s.name == "main" and s.kind == "function" for s in symbols)

    def test_struct(self, tmp_path):
        f = tmp_path / "types.go"
        f.write_text("type User struct {\n\tName string\n}\n")
        symbols = list_symbols(str(f))
        assert any(s.name == "User" and s.kind == "struct" for s in symbols)

    def test_exported(self, tmp_path):
        f = tmp_path / "api.go"
        f.write_text("func HandleRequest() {}\nfunc helper() {}\n")
        symbols = list_symbols(str(f))
        exported = [s for s in symbols if s.exported]
        assert len(exported) == 1
        assert exported[0].name == "HandleRequest"


class TestListSymbolsRust:

    def test_function(self, tmp_path):
        f = tmp_path / "lib.rs"
        f.write_text("pub fn process(data: &str) -> String {\n    data.to_string()\n}\n")
        symbols = list_symbols(str(f))
        assert any(s.name == "process" and s.kind == "function" for s in symbols)

    def test_struct(self, tmp_path):
        f = tmp_path / "lib.rs"
        f.write_text("pub struct Config {\n    pub name: String,\n}\n")
        symbols = list_symbols(str(f))
        assert any(s.name == "Config" and s.kind == "struct" for s in symbols)

    def test_trait(self, tmp_path):
        f = tmp_path / "lib.rs"
        f.write_text("pub trait Handler {\n    fn handle(&self);\n}\n")
        symbols = list_symbols(str(f))
        assert any(s.name == "Handler" and s.kind == "trait" for s in symbols)

    def test_exported(self, tmp_path):
        f = tmp_path / "lib.rs"
        f.write_text("pub fn api() {}\nfn internal() {}\n")
        symbols = list_symbols(str(f))
        exported = [s for s in symbols if s.exported]
        assert len(exported) == 1


class TestFindDefinition:

    def test_finds_across_files(self, tmp_path):
        (tmp_path / "a.js").write_text("function hello() {}\n")
        (tmp_path / "b.ts").write_text("function hello() {}\n")
        results = find_definition("hello", str(tmp_path))
        assert len(results) >= 2

    def test_not_found(self, tmp_path):
        (tmp_path / "a.js").write_text("function other() {}\n")
        results = find_definition("missing", str(tmp_path))
        assert len(results) == 0


class TestFindReferences:

    def test_finds_refs(self, tmp_path):
        (tmp_path / "a.js").write_text("function hello() {}\nhello();\n")
        (tmp_path / "b.js").write_text("import { hello } from './a';\nhello();\n")
        results = find_references("hello", str(tmp_path))
        assert len(results) >= 3


class TestFindImports:

    def test_js_imports(self, tmp_path):
        f = tmp_path / "app.js"
        f.write_text("import React from 'react';\nconst fs = require('fs');\n")
        imports = find_imports(str(f))
        assert "react" in imports
        assert "fs" in imports

    def test_go_imports(self, tmp_path):
        f = tmp_path / "main.go"
        f.write_text('import (\n\t"fmt"\n\t"os"\n)\n')
        imports = find_imports(str(f))
        assert "fmt" in imports
        assert "os" in imports

    def test_rust_imports(self, tmp_path):
        f = tmp_path / "lib.rs"
        f.write_text("use std::collections::HashMap;\nuse crate::config;\n")
        imports = find_imports(str(f))
        assert any("std" in i for i in imports)

    def test_c_includes(self, tmp_path):
        f = tmp_path / "main.c"
        f.write_text('#include <stdio.h>\n#include "utils.h"\n')
        imports = find_imports(str(f))
        assert "stdio.h" in imports
        assert "utils.h" in imports


class TestProjectLanguages:

    def test_counts(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1\n")  # not in LANG_MAP
        (tmp_path / "b.js").write_text("x = 1;\n")
        (tmp_path / "c.ts").write_text("x = 1;\n")
        (tmp_path / "d.go").write_text("x := 1\n")
        langs = project_languages(str(tmp_path))
        assert "javascript" in langs
        assert "typescript" in langs
        assert "go" in langs

    def test_empty(self, tmp_path):
        assert project_languages(str(tmp_path)) == {}


class TestEdgeCases:

    def test_missing_file(self):
        symbols = list_symbols("/nonexistent.js")
        assert symbols == []

    def test_unknown_language(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("a,b,c\n")
        symbols = list_symbols(str(f))
        assert symbols == []

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.go"
        f.write_text("")
        symbols = list_symbols(str(f))
        assert symbols == []
